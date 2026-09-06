# Real-industry P&ID samples — sources & licensing

이 디렉터리의 PDF는 **본 데모의 합성 도면 외에 실제 산업 P&ID에서도 동일한 파이프라인이 동작함**을 보이기 위한 자산입니다.

US Federal works은 17 U.S.C. § 105에 따라 자동으로 public domain입니다. 본 자산들은 모두 NREL (National Renewable Energy Laboratory, US DOE 산하)에서 발간한 공식 보고서 부록의 P&ID 도면입니다.

---

## real-01_nrel_hd_hystep.pdf

- **출처 보고서**: *Heavy-Duty Hydrogen Station Equipment Performance Device (HD HyStEP)*
- **저자/기관**: National Renewable Energy Laboratory (NREL), US DOE
- **문서 ID**: NREL/TP-5700-96170
- **발간일**: September 2025
- **공식 URL**: https://docs.nrel.gov/docs/fy25osti/96170.pdf
- **라이선스**: US Federal government work — public domain (17 U.S.C. § 105)
- **인용 문구**: "This work was authored by NREL for the U.S. Department of Energy (DOE), operated under Contract No. DE-AC36-08GO28308 ... This report is available at no cost from NREL at www.nrel.gov/publications."

**P&ID 페이지**: pp. 11–16 (Appendix A, 6-sheet 세트):
1. Interconnection Piping
2. Storage Tanks 01
3. Storage Tanks 02
4. Valve Manifold
5. Trailer
6. (cover/legend)

**내용**: 상용 수소 충전 시험 장치의 multi-sheet 벡터 P&ID. 25+ 태깅된 튜빙 라인, TK-1~TK-12 저장조 (PV/PE/TE 계장), 24+ AOV 액추에이트 밸브 매니폴드, combustible-gas/fire/oxygen/ambient-temp 안전 계장.

---

## real-02_nrel_molten_salt.pdf

- **출처 보고서**: *Saltstream 700 — Molten Salt Forced Convection Loop Final Test Report*
- **저자/기관**: National Renewable Energy Laboratory (NREL), US DOE
- **문서 ID**: NREL/SR-5200-58595
- **발간일**: May 2013
- **공식 URL**: https://docs.nrel.gov/docs/fy13osti/58595.pdf
- **라이선스**: US Federal government work — public domain (17 U.S.C. § 105)
- **인용 문구**: "NREL is a national laboratory of the U.S. Department of Energy, Office of Energy Efficiency & Renewable Energy ... This report was prepared as an account of work sponsored by an agency of the United States government."

**P&ID 페이지**: p. 11 (Figure 1, single-page P&ID)

**내용**: 700°C / 500°C 듀얼 탱크 molten-salt 열에너지 저장 루프. 50+ 태그 (TE-201~TE-405, FE-201, FV-201, HV-202, PT-101 등), 3개 컨트롤 루프, 벤트/N2 퍼지 라인. 단일 페이지로 자기 완결.

---

## 백업 후보 (현재 사용 안 함)

라이선스는 클리어하지만 본 데모에는 NREL 2장이 더 적합해 채택하지 않았습니다:

- **NREL Empire Energy 지열 발전소** (NREL/CP-550-30275, 2001) — 스캔본, 40+ 계장 태그
- **EPA Process-Based Investigation Guide 부록 E** (EPA-330/9-97-001, 1997) — 산업 폐수 P&ID, 스캔본

---

## 데모에서의 사용 정책

- 이 도면들은 **합성 도면(01, 01b, 02, 03, 04) 외 추가 자산**으로 라이브 데모에서만 사용
- ground-truth 데이터가 없으므로 P/R/F1 metric은 **표시하지 않음**
- 사이드바에서 별도 그룹 "REAL SAMPLES (live, no metric)"로 분리
- 라이브 추출만 가능 (cached replay 없음)

이 정책의 근거는 v6 spec `docs/superpowers/specs/2026-05-23-v6-bugfix-real-samples-cinematic-design.md` §B 참조.
