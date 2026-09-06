import { Loader2, Upload } from "lucide-react";
import { useRef, useState } from "react";

import { api } from "@/api/client";
import { Button } from "@/components/atoms/Button";

interface Props {
  onUploaded: (drawingId: string, fileName: string) => void;
  disabled?: boolean;
}

export function UploadButton({ onUploaded, disabled }: Props) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onPick = () => {
    setError(null);
    inputRef.current?.click();
  };

  const onChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setPending(true);
    try {
      const res = await api.uploadDrawing(file);
      onUploaded(res.drawing_id, file.name);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setPending(false);
    }
  };

  return (
    <div className="flex flex-col gap-1">
      <Button
        variant="outline"
        size="sm"
        onClick={onPick}
        disabled={disabled || pending}
        aria-label="Upload PDF or image"
      >
        {pending ? (
          <Loader2 aria-hidden className="animate-spin" size={14} />
        ) : (
          <Upload aria-hidden size={14} />
        )}
        <span>Upload PDF or image</span>
      </Button>
      <input
        ref={inputRef}
        type="file"
        className="hidden"
        accept=".pdf,.png,.jpg,.jpeg,.tif,.tiff,application/pdf,image/png,image/jpeg,image/tiff"
        onChange={onChange}
      />
      {error ? (
        <span className="text-xs text-danger" role="alert">{error}</span>
      ) : null}
    </div>
  );
}
