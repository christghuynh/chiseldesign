import { type ChangeEvent, useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import { ErrorState } from "../components/common/ErrorState";
import { LoadingState } from "../components/common/LoadingState";
import { useStore } from "../store";
import type { TemplateInfo } from "../types";
import { missingRequired, setCaptureSession, specFromDefaults } from "./flowState";
import { IMAGE_ACCEPT, IMAGE_TYPES_TEXT, isAcceptedImage } from "./uploadImage";

type Fields = "total_rise_in" | "available_length_in" | "clear_width_in" | "contractor_quote_cad" | "note";
const blank = { total_rise_in: "", available_length_in: "", clear_width_in: "", contractor_quote_cad: "", note: "" };

function TemplateBlueprint({ template }: { template: TemplateInfo }) {
  const isRamp = template.key.toLowerCase().includes("ramp");
  return (
    <div className="template-preview-art" aria-hidden="true">
      <svg viewBox="0 0 360 210" role="presentation">
        <path d="M27 42H333M27 84H333M27 126H333M27 168H333M74 21V189M122 21V189M170 21V189M218 21V189M266 21V189" className="template-preview-art__grid" />
        {isRamp ? <>
          <path d="M44 154H110L221 62H306" className="template-preview-art__main" />
          <path d="M44 172H118L229 80H306" className="template-preview-art__thin" />
          <path d="M66 154v18M110 154v18M147 123v18M184 92v18M221 62v18M264 62v18M306 62v18" className="template-preview-art__detail" />
          <path d="M75 140V99h34M129 111V70h34M183 70V38h34" className="template-preview-art__rail" />
        </> : <>
          <rect x="70" y="56" width="220" height="104" rx="12" className="template-preview-art__main template-preview-art__shape" />
          <path d="M100 160V101l80-55 80 55v59M150 160v-38h60v38M118 105h26M216 105h26" className="template-preview-art__detail" />
        </>}
        <circle cx="44" cy={isRamp ? "154" : "160"} r="7" className="template-preview-art__node" />
        <circle cx="306" cy={isRamp ? "62" : "160"} r="7" className="template-preview-art__node" />
      </svg>
      <span>Preview</span>
    </div>
  );
}

export function Capture() {
  const setScreen = useStore((state) => state.setScreen);
  const setCurrentProjectId = useStore((state) => state.setCurrentProjectId);
  const picker = useRef<HTMLInputElement>(null);
  const camera = useRef<HTMLInputElement>(null);
  const photoCard = useRef<HTMLDivElement>(null);
  const cameraPreview = useRef<HTMLVideoElement>(null);
  const cameraStream = useRef<MediaStream | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  // Most browsers other than Safari can't display HEIC; the server still reads it.
  const [previewFailed, setPreviewFailed] = useState(false);
  const [templates, setTemplates] = useState<TemplateInfo[]>([]);
  const [templateKey, setTemplateKey] = useState("ramp");
  const [templatePickerOpen, setTemplatePickerOpen] = useState(false);
  const [previewTemplateKey, setPreviewTemplateKey] = useState("ramp");
  const [cameraOpen, setCameraOpen] = useState(false);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [photoAttention, setPhotoAttention] = useState(false);
  const [fields, setFields] = useState(blank);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const setField = (key: Fields, value: string) => setFields((current) => ({ ...current, [key]: value }));
  const numberOrUndefined = (value: string) => value.trim() === "" ? undefined : Number(value);

  useEffect(() => {
    void api.templates().then(setTemplates).catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "Could not load templates."));
  }, []);

  useEffect(() => () => {
    cameraStream.current?.getTracks().forEach((track) => track.stop());
  }, []);

  function choose(next: File | undefined) {
    setError(null);
    setPhotoAttention(false);
    if (!next) return;
    if (!isAcceptedImage(next)) { setError(`Please choose an image file (${IMAGE_TYPES_TEXT}).`); return; }
    if (next.size > 10 * 1024 * 1024) { setError("That image is larger than 10 MB. Choose a smaller image."); return; }
    if (preview) URL.revokeObjectURL(preview);
    setFile(next);
    setPreviewFailed(false);
    setPreview(URL.createObjectURL(next));
  }

  function closeCamera() {
    cameraStream.current?.getTracks().forEach((track) => track.stop());
    cameraStream.current = null;
    if (cameraPreview.current) cameraPreview.current.srcObject = null;
    setCameraOpen(false);
    setCameraError(null);
  }

  async function openCamera() {
    if (!navigator.mediaDevices?.getUserMedia) {
      camera.current?.click();
      return;
    }
    setCameraError(null);
    setCameraOpen(true);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: "environment" } }, audio: false });
      cameraStream.current = stream;
      if (cameraPreview.current) {
        cameraPreview.current.srcObject = stream;
        await cameraPreview.current.play();
      }
    } catch (reason) {
      setCameraError(reason instanceof Error && reason.name === "NotAllowedError" ? "Camera access was blocked. Allow camera access in your browser settings and try again." : "We could not open your camera. You can still choose an image from your device.");
    }
  }

  function takePhoto() {
    const video = cameraPreview.current;
    if (!video || video.videoWidth === 0 || video.videoHeight === 0) return;
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext("2d")?.drawImage(video, 0, 0, canvas.width, canvas.height);
    canvas.toBlob((blob) => {
      if (!blob) return;
      choose(new File([blob], "chisel-camera-photo.jpg", { type: "image/jpeg" }));
      closeCamera();
    }, "image/jpeg", .92);
  }

  async function submit() {
    if (!file) {
      setError("Add a photo in the highlighted area before analyzing it. To start without one, use Browse templates.");
      setPhotoAttention(false);
      window.requestAnimationFrame(() => {
        setPhotoAttention(true);
        photoCard.current?.scrollIntoView({ behavior: "smooth", block: "center" });
      });
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await api.parse(file, {
        total_rise_in: numberOrUndefined(fields.total_rise_in),
        available_length_in: numberOrUndefined(fields.available_length_in),
        clear_width_in: numberOrUndefined(fields.clear_width_in),
        contractor_quote_cad: numberOrUndefined(fields.contractor_quote_cad),
      }, fields.note);
      if (!result.spec) { setError("We could not identify a supported project from this image. Pick a ramp template manually."); return; }
      setCurrentProjectId(null);
      setCaptureSession({ parse: result, imageUrl: preview });
      setScreen("confirm");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The photo could not be analyzed. Try again or pick a template.");
    } finally {
      setLoading(false);
    }
  }

  async function startTemplate(key = templateKey) {
    const template = templates.find((item) => item.key === key);
    if (!template) return;
    setError(null);
    // Start from the template's own defaults; /generate rejects a request missing required params.
    const known = (template.params_schema.properties ?? {}) as Record<string, unknown>;
    const values: Record<string, number | undefined> = {};
    (["total_rise_in", "available_length_in", "clear_width_in"] as const).forEach((key) => {
      if (key in known && fields[key].trim()) values[key] = Number(fields[key]);
    });
    const spec = specFromDefaults(template, values, { contractor_quote_cad: numberOrUndefined(fields.contractor_quote_cad), notes: fields.note });
    const missing = missingRequired(template, spec);
    if (missing.length) {
      setError(`Enter ${missing.map((name) => name.replaceAll("_", " ").replace(/ in$/, " (inches)")).join(", ")} to start the ${template.name.toLowerCase()} template.`);
      return;
    }
    setLoading(true);
    try {
      setCurrentProjectId(null);
      setCaptureSession({ parse: { spec, template_confidence: null, questions: [], raw_notes: "Template selected manually." }, imageUrl: null });
      setScreen("confirm");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not start the selected template.");
    } finally {
      setLoading(false);
    }
  }

  const fieldInputs: [Fields, string][] = [
    ["total_rise_in", "Total rise (inches)"],
    ["available_length_in", "Available length (inches)"],
    ["clear_width_in", "Desired width (inches)"],
    ["contractor_quote_cad", "Contractor quote (CAD)"],
  ];
  const previewTemplate = templates.find((template) => template.key === previewTemplateKey) ?? templates[0] ?? null;

  function openTemplatePicker() {
    setPreviewTemplateKey(templateKey);
    setTemplatePickerOpen(true);
  }

  return (
    <section aria-labelledby="capture-title" className="capture-page mx-auto">
      <div className="capture-page__heading">
        <h2 id="capture-title">Capture</h2>
        <div className="capture-page__heading-actions">
          <p>Add a photo and any measurements you have, or start from a template.</p>
          <button type="button" className="app-button app-button--secondary" onClick={openTemplatePicker} disabled={!templates.length}>Browse templates</button>
        </div>
      </div>
      {error && <div className={`capture-error ${photoAttention ? "capture-error--photo" : ""}`}><ErrorState message={error} onRetry={file ? () => void submit() : undefined} /></div>}
      {loading && <LoadingState message={file ? "Reading your photo and measurements…" : "Preparing your template…"} />}
      <div className="capture-workspace">
        <div ref={photoCard} className={`app-card capture-card capture-photo ${photoAttention ? "capture-photo--attention" : ""}`}>
          <div>
            <h3><span className="capture-step">1</span>Add a photo</h3>
            <p className="capture-card__intro">A sketch or a photo of the space works. Images up to 10 MB.</p>
          </div>
          <input ref={picker} className="sr-only" type="file" accept={IMAGE_ACCEPT} onChange={(event: ChangeEvent<HTMLInputElement>) => choose(event.target.files?.[0])} />
          <input ref={camera} className="sr-only" type="file" accept={IMAGE_ACCEPT} capture="environment" onChange={(event: ChangeEvent<HTMLInputElement>) => choose(event.target.files?.[0])} />
          {preview && previewFailed ? <div className="capture-dropzone" role="status"><p>Selected <strong>{file?.name}</strong>. This browser can't preview this format, but it will be read when you analyze it.</p></div> : preview ? <img src={preview} alt="Selected site or sketch" className="capture-preview" onError={() => setPreviewFailed(true)} /> : <div className="capture-dropzone"><p>No image selected yet. A photo is optional if you would rather begin with a template.</p></div>}
          {photoAttention && !preview && <p className="capture-photo__required" role="status">Add or take a photo here before analyzing.</p>}
          <div className="mt-3 flex flex-wrap gap-2">
            <button type="button" className="app-button app-button--secondary flex flex-1 items-center justify-center gap-2 border-dashed" onClick={() => picker.current?.click()} onDragOver={(event) => event.preventDefault()} onDrop={(event) => { event.preventDefault(); choose(event.dataTransfer.files[0]); }}>
              <svg aria-hidden="true" viewBox="0 0 24 24" className="h-5 w-5 fill-none stroke-current" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="4" width="18" height="16" rx="2" /><circle cx="8" cy="9" r="1.2" /><path d="m4 18 5.2-5 3.5 3.2 2.3-2.2L20 18" /></svg>
              Choose an image
            </button>
            <button type="button" className="app-button app-button--secondary inline-flex items-center justify-center gap-2" onClick={() => void openCamera()}>
              <svg aria-hidden="true" viewBox="0 0 24 24" className="h-5 w-5 fill-none stroke-current" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M4 8h3l1.3-2h7.4L17 8h3a1.5 1.5 0 0 1 1.5 1.5v8A1.5 1.5 0 0 1 20 19H4a1.5 1.5 0 0 1-1.5-1.5v-8A1.5 1.5 0 0 1 4 8Z" /><circle cx="12" cy="13" r="3.2" /></svg>
              Use camera
            </button>
          </div>
        </div>
        <div className="app-card capture-card">
          <h3><span className="capture-step">2</span>Add what you know</h3>
          <p className="capture-card__intro">Leave anything blank if you are not sure yet.</p>
          <div className="capture-fields">
            {fieldInputs.map(([key, label]) => <label key={key}>{label}<input className="app-input mt-1 w-full" type="number" min="0" value={fields[key]} onChange={(event) => setField(key, event.target.value)} /></label>)}
            <label className="capture-notes">Notes<textarea className="app-input mt-1 w-full" value={fields.note} onChange={(event) => setField("note", event.target.value)} /></label>
          </div>
          <button type="button" className="app-button mt-3 w-full" disabled={loading} onClick={() => void submit()}>Analyze photo</button>
        </div>
      </div>
      {templatePickerOpen && previewTemplate && (
        <div className="template-selector-backdrop" role="presentation">
          <section className="app-card template-selector" role="dialog" aria-modal="true" aria-labelledby="template-selector-title">
            <div className="template-selector__header">
              <div><p className="template-selector__eyebrow">Start from a template</p><h2 id="template-selector-title">Choose your project</h2></div>
              <button type="button" className="app-button app-button--secondary app-icon-button" onClick={() => setTemplatePickerOpen(false)} aria-label="Close template selector">×</button>
            </div>
            <div className="template-selector__body">
              <div className="template-selector__list" aria-label="Available templates">
                {templates.map((template) => <button type="button" key={template.key} className={`template-selector__item ${template.key === previewTemplate.key ? "template-selector__item--selected" : ""}`} onClick={() => setPreviewTemplateKey(template.key)} aria-pressed={template.key === previewTemplate.key}>
                  <span>{template.name}</span><small>{template.description}</small>
                </button>)}
              </div>
              <aside className="template-selector__preview" aria-label={`${previewTemplate.name} preview`}>
                <TemplateBlueprint template={previewTemplate} />
                <h3>{previewTemplate.name}</h3>
                <p>{previewTemplate.description}</p>
                <div className="template-selector__defaults">
                  {Object.entries(previewTemplate.defaults).slice(0, 3).map(([key, value]) => <span key={key}>{key.replaceAll("_", " ")}: {String(value ?? "auto")}</span>)}
                </div>
                <button type="button" className="app-button w-full" disabled={loading} onClick={() => { setTemplateKey(previewTemplate.key); setTemplatePickerOpen(false); void startTemplate(previewTemplate.key); }}>Start with this template</button>
              </aside>
            </div>
          </section>
        </div>
      )}
      {cameraOpen && (
        <div className="camera-capture-backdrop" role="presentation">
          <section className="app-card camera-capture" role="dialog" aria-modal="true" aria-labelledby="camera-capture-title">
            <div className="camera-capture__header">
              <div><p className="template-selector__eyebrow">Camera</p><h2 id="camera-capture-title">Take a photo</h2></div>
              <button type="button" className="app-button app-button--secondary app-icon-button" onClick={closeCamera} aria-label="Close camera">×</button>
            </div>
            {cameraError ? <div className="camera-capture__error"><p>{cameraError}</p><button type="button" className="app-button app-button--secondary" onClick={() => void openCamera()}>Try again</button></div> : <video ref={cameraPreview} className="camera-capture__video" autoPlay muted playsInline />}
            <div className="camera-capture__actions">
              <button type="button" className="app-button app-button--secondary" onClick={closeCamera}>Cancel</button>
              {!cameraError && <button type="button" className="app-button" onClick={takePhoto}>Take photo</button>}
            </div>
          </section>
        </div>
      )}
    </section>
  );
}
