import { describe, expect, it } from "vitest";
import { isAcceptedImage } from "./uploadImage";

describe("isAcceptedImage", () => {
  it.each([
    ["sketch.png", "image/png"],
    ["IMG_0042.HEIC", "image/heic"],
    ["IMG_0042.HEIC", ""], // Chrome on Windows/Linux often reports no type for HEIC
    ["photo.heif", "application/octet-stream"],
    ["porch.avif", ""],
    ["scan.TIFF", ""],
    ["camera", "image/jpeg"],
  ])("accepts %s (%s)", (name, type) => {
    expect(isAcceptedImage({ name, type })).toBe(true);
  });

  it.each([
    ["notes.pdf", "application/pdf"],
    ["sketch.txt", "text/plain"],
    ["noextension", ""],
  ])("rejects %s (%s)", (name, type) => {
    expect(isAcceptedImage({ name, type })).toBe(false);
  });
});
