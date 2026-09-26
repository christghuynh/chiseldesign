import { describe, expect, it } from "vitest";
import { matchVoiceCommand, VOICE_HELP } from "./voiceCommands";

describe("matchVoiceCommand", () => {
  it.each([
    ["next", "next"],
    ["Next.", "next"],
    ["next step please", "next"],
    ["go forward", "next"],
    ["back", "back"],
    ["Go back!", "back"],
    ["previous", "back"],
    ["previous step", "back"],
    ["repeat", "repeat"],
    ["Can you repeat that?", "repeat"],
    ["say that again", "repeat"],
    ["stop", "stop"],
    ["STOP", "stop"],
    ["pause", "stop"],
  ])("%j -> %s", (phrase, action) => {
    expect(matchVoiceCommand(phrase)).toBe(action);
  });

  it.each(["", "   ", "make it wider", "nextdoor", "backyard ramp", "repeated"])("%j -> null (no whole keyword)", (phrase) => {
    expect(matchVoiceCommand(phrase)).toBeNull();
  });

  it("takes the first keyword when a phrase has several", () => {
    expect(matchVoiceCommand("stop, go back")).toBe("stop");
    expect(matchVoiceCommand("back, no, next")).toBe("back");
  });

  it("has a short help phrase", () => {
    expect(VOICE_HELP).toBe("Say next, back, or repeat.");
  });
});
