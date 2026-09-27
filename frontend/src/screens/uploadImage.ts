// Which uploads the Capture screen accepts. The backend decodes and validates every image (INF-8),
// so this only has to avoid rejecting good files. Browsers often give HEIC/HEIF files (iPhone
// photos) an empty or odd MIME type, so the file extension counts too.
const EXTENSIONS = ["jpg", "jpeg", "png", "heic", "heif", "webp", "avif", "gif", "bmp", "tif", "tiff"];

/** `accept` for <input type="file">: any image, plus extensions some pickers don't map to image/*. */
export const IMAGE_ACCEPT = "image/*,.heic,.heif,.avif";

/** Human-readable list for messages. */
export const IMAGE_TYPES_TEXT = "JPEG, PNG, HEIC, WebP, AVIF, GIF, BMP or TIFF";

export function isAcceptedImage(file: { name: string; type: string }): boolean {
  if (file.type.startsWith("image/")) return true;
  const ext = file.name.toLowerCase().split(".").pop() ?? "";
  return EXTENSIONS.includes(ext);
}
