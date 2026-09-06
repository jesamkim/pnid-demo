/**
 * Lambda@Edge viewer-request handler — gates CloudFront on a Cognito
 * Hosted UI session.
 *
 * Flow:
 *   1) request comes in
 *   2) if request is to /__auth/callback, exchange `code` for tokens,
 *      verify the id_token, set HttpOnly cookie, redirect to "/"
 *   3) if request has the cookie + cookie verifies → forward
 *   4) otherwise → 302 to Cognito Hosted UI authorize endpoint
 *
 * Token verification uses the Cognito JWKS, fetched once per cold start
 * and cached in module scope. For Lambda@Edge that means up to one
 * fetch per replicated edge location per cold start — acceptable.
 *
 * Build-time placeholders (replaced by CDK before bundling):
 *   __USER_POOL_ID__
 *   __APP_CLIENT_ID__
 *   __HOSTED_UI_HOSTNAME__         e.g. "pnid-demo-xxxxxx.auth.us-east-1.amazoncognito.com"
 *   __REGION__                     "us-east-1"
 *
 * The CloudFront distribution hostname is read from the incoming
 * request's Host header at runtime so we don't need to bake a token-y
 * value into the function source.
 *
 * No external dependencies — pure Node 20 stdlib + crypto. Keeps the
 * package well under the 1 MB Lambda@Edge limit.
 */
"use strict";

const https = require("https");
const crypto = require("crypto");

const USER_POOL_ID = "__USER_POOL_ID__";
const APP_CLIENT_ID = "__APP_CLIENT_ID__";
const HOSTED_UI_HOST = "__HOSTED_UI_HOSTNAME__";
const REGION = "__REGION__";

const JWKS_URL = `https://cognito-idp.${REGION}.amazonaws.com/${USER_POOL_ID}/.well-known/jwks.json`;
const ISSUER = `https://cognito-idp.${REGION}.amazonaws.com/${USER_POOL_ID}`;
const COOKIE_NAME = "__pnid_id_token";
const COOKIE_MAX_AGE_S = 3600;

function distributionHost(headers) {
  // Lambda@Edge viewer-request: request headers include the original
  // viewer Host header. CloudFront synthesises this for us.
  return (headers.host && headers.host[0] && headers.host[0].value) || "";
}

function redirectUri(headers) {
  return `https://${distributionHost(headers)}/__auth/callback`;
}

let JWKS_CACHE = null;

function fetchJson(url) {
  return new Promise((resolve, reject) => {
    https
      .get(url, (res) => {
        let buf = "";
        res.on("data", (chunk) => (buf += chunk));
        res.on("end", () => {
          try {
            resolve(JSON.parse(buf));
          } catch (e) {
            reject(e);
          }
        });
      })
      .on("error", reject);
  });
}

async function getJwks() {
  if (JWKS_CACHE) return JWKS_CACHE;
  JWKS_CACHE = await fetchJson(JWKS_URL);
  return JWKS_CACHE;
}

function base64UrlDecode(str) {
  str = str.replace(/-/g, "+").replace(/_/g, "/");
  while (str.length % 4) str += "=";
  return Buffer.from(str, "base64");
}

function pemFromJwk(jwk) {
  const n = base64UrlDecode(jwk.n);
  const e = base64UrlDecode(jwk.e);
  const key = crypto.createPublicKey({
    key: { kty: "RSA", n: jwk.n, e: jwk.e },
    format: "jwk",
  });
  return key.export({ type: "spki", format: "pem" });
}

async function verifyIdToken(token) {
  const parts = token.split(".");
  if (parts.length !== 3) throw new Error("malformed jwt");
  const [headerB64, payloadB64, sigB64] = parts;
  const header = JSON.parse(base64UrlDecode(headerB64).toString("utf8"));
  const payload = JSON.parse(base64UrlDecode(payloadB64).toString("utf8"));

  const jwks = await getJwks();
  const jwk = jwks.keys.find((k) => k.kid === header.kid);
  if (!jwk) throw new Error("kid not found in jwks");

  const verifier = crypto.createVerify(
    header.alg === "RS256" ? "RSA-SHA256" : header.alg.replace("RS", "RSA-SHA"),
  );
  verifier.update(`${headerB64}.${payloadB64}`);
  const ok = verifier.verify(pemFromJwk(jwk), base64UrlDecode(sigB64));
  if (!ok) throw new Error("signature mismatch");

  if (payload.iss !== ISSUER) throw new Error("bad issuer");
  if (payload.aud !== APP_CLIENT_ID) throw new Error("bad aud");
  if (payload.token_use !== "id") throw new Error("not id token");
  if (payload.exp <= Math.floor(Date.now() / 1000)) throw new Error("expired");

  return payload;
}

function readCookie(headers, name) {
  const c = headers.cookie?.[0]?.value || "";
  for (const part of c.split(";")) {
    const [k, v] = part.trim().split("=");
    if (k === name) return decodeURIComponent(v || "");
  }
  return null;
}

function redirectToLogin(headers) {
  const state = crypto.randomBytes(8).toString("hex");
  const url =
    `https://${HOSTED_UI_HOST}/oauth2/authorize` +
    `?client_id=${encodeURIComponent(APP_CLIENT_ID)}` +
    `&response_type=code` +
    `&scope=${encodeURIComponent("openid email")}` +
    `&redirect_uri=${encodeURIComponent(redirectUri(headers))}` +
    `&state=${state}`;
  return {
    status: "302",
    statusDescription: "Found",
    headers: {
      location: [{ key: "Location", value: url }],
      "cache-control": [{ key: "Cache-Control", value: "no-store" }],
    },
  };
}

function postForm(host, path, params) {
  const body = new URLSearchParams(params).toString();
  return new Promise((resolve, reject) => {
    const req = https.request(
      {
        method: "POST",
        host,
        path,
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
          "Content-Length": Buffer.byteLength(body),
        },
      },
      (res) => {
        let buf = "";
        res.on("data", (c) => (buf += c));
        res.on("end", () => {
          try {
            resolve({ status: res.statusCode, body: JSON.parse(buf) });
          } catch (e) {
            resolve({ status: res.statusCode, body: { raw: buf } });
          }
        });
      },
    );
    req.on("error", reject);
    req.write(body);
    req.end();
  });
}

async function exchangeCodeForTokens(code, headers) {
  const result = await postForm(HOSTED_UI_HOST, "/oauth2/token", {
    grant_type: "authorization_code",
    client_id: APP_CLIENT_ID,
    code,
    redirect_uri: redirectUri(headers),
  });
  if (result.status !== 200 || !result.body.id_token) {
    throw new Error(`token exchange failed: ${JSON.stringify(result)}`);
  }
  return result.body;
}

exports.handler = async (event) => {
  const request = event.Records[0].cf.request;
  const headers = request.headers || {};
  const uri = request.uri || "/";

  // 1) Callback path: exchange code for tokens, set cookie, redirect to "/".
  if (uri.startsWith("/__auth/callback")) {
    const qs = new URLSearchParams(request.querystring || "");
    const code = qs.get("code");
    if (!code) {
      return {
        status: "400",
        statusDescription: "Bad Request",
        body: "missing code",
      };
    }
    try {
      const tokens = await exchangeCodeForTokens(code, headers);
      await verifyIdToken(tokens.id_token);
      return {
        status: "302",
        statusDescription: "Found",
        headers: {
          location: [{ key: "Location", value: "/" }],
          "set-cookie": [
            {
              key: "Set-Cookie",
              value:
                `${COOKIE_NAME}=${encodeURIComponent(tokens.id_token)}` +
                `; Path=/; Secure; HttpOnly; SameSite=Lax; Max-Age=${COOKIE_MAX_AGE_S}`,
            },
          ],
          "cache-control": [{ key: "Cache-Control", value: "no-store" }],
        },
      };
    } catch (err) {
      return {
        status: "401",
        statusDescription: "Unauthorized",
        body: `auth error: ${err.message}`,
      };
    }
  }

  // 2) Try cookie.
  const token = readCookie(headers, COOKIE_NAME);
  if (token) {
    try {
      await verifyIdToken(token);
      return request; // forward
    } catch (_) {
      // fall through to login
    }
  }

  // 3) No / bad cookie — redirect to Hosted UI.
  return redirectToLogin(headers);
};
