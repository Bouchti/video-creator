import React from "react";
import { Composition } from "remotion";
import { BridgeShort, BRIDGE_FRAMES } from "./videos/bridge/Bridge";
import { PisaShort, PISA_FRAMES } from "./videos/pisa/Pisa";
import { EscalatorShort, ESC_FRAMES } from "./videos/escalator/Escalator";
import { ChipShort, CHIP_FRAMES } from "./videos/chip/Chip";
import { EiffelShort, EIFFEL_FRAMES } from "./videos/eiffel/Eiffel";
import { EmuSheet } from "./videos/emu/Sheet";
import { EmuShort, EMU_FRAMES } from "./videos/emu/Emu";
import { WhaleShort, WHALE_FRAMES } from "./videos/whale/Whale";
import { MikeShort, MIKE_FRAMES } from "./videos/mike/Mike";
import { MolassesShort, MOLASSES_FRAMES } from "./videos/molasses/Molasses";
import { MarathonShort, MARATHON_FRAMES } from "./videos/marathon/Marathon";

export const Root: React.FC = () => (
  <>
    <Composition id="BridgeShort" component={BridgeShort} durationInFrames={BRIDGE_FRAMES} fps={30} width={1080} height={1920} />
    <Composition id="EscalatorShort" component={EscalatorShort} durationInFrames={ESC_FRAMES} fps={30} width={1080} height={1920} />
    <Composition id="ChipShort" component={ChipShort} durationInFrames={CHIP_FRAMES} fps={30} width={1080} height={1920} />
    <Composition id="EiffelShort" component={EiffelShort} durationInFrames={EIFFEL_FRAMES} fps={30} width={1080} height={1920} />
    <Composition id="EmuShort" component={EmuShort} durationInFrames={EMU_FRAMES} fps={30} width={1080} height={1920} />
    <Composition id="WhaleShort" component={WhaleShort} durationInFrames={WHALE_FRAMES} fps={30} width={1080} height={1920} />
    <Composition id="MikeShort" component={MikeShort} durationInFrames={MIKE_FRAMES} fps={30} width={1080} height={1920} />
    <Composition id="MolassesShort" component={MolassesShort} durationInFrames={MOLASSES_FRAMES} fps={30} width={1080} height={1920} />
    <Composition id="MarathonShort" component={MarathonShort} durationInFrames={MARATHON_FRAMES} fps={30} width={1080} height={1920} />
    <Composition id="EmuSheet" component={EmuSheet} durationInFrames={60} fps={30} width={1080} height={1920} />
    <Composition id="PisaShort" component={PisaShort} durationInFrames={PISA_FRAMES} fps={30} width={1080} height={1920} />
  </>
);
