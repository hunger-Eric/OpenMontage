import React from "react";
import {AbsoluteFill, Audio, Freeze, Img, OffthreadVideo, Sequence, staticFile, useCurrentFrame} from "remotion";

// All positions, timing and material choices are authored in the proposal/edit.
// This renderer only executes the frozen timeline; it does not choose a story.
type Clip = {id: string; src: string; kind: "image" | "video"; from: number; duration: number;
  trimBefore: number; playbackRate: number; fade_frames: number; pictureFrames: number};
type Cue = {id: string; start_frame: number; end_frame: number; text: string;
  style: {left: number; top: number; width: number; height: number; fontSize: number; fontFamily: string;
    fontWeight: number; color: string; strokeColor: string; strokeWidth: number;
    fade_frames?: number; entrance_scale?: number}};
export type ReferenceReplicaProps = {fps: number; width: number; height: number; total_frames: number;
  clips: Clip[]; captions: Cue[]; audioSrc: string | null; backgroundColor: string};
const src = (path: string) => /^(https?:|data:)/.test(path) ? path : staticFile(path);
const Picture: React.FC<{clip: Clip}> = ({clip}) => {
  const frame = useCurrentFrame();
  const opacity = clip.fade_frames > 0 ? Math.min(1, frame / clip.fade_frames) : 1;
  const style: React.CSSProperties = {width: "100%", height: "100%", objectFit: "contain", opacity};
  return clip.kind === "image" ? <Img src={src(clip.src)} style={style}/> :
    <Freeze frame={Math.min(frame, clip.pictureFrames - 1)}>
      <OffthreadVideo src={src(clip.src)} startFrom={clip.trimBefore} playbackRate={clip.playbackRate} muted style={style}/>
    </Freeze>;
};
const Caption: React.FC<{cue: Cue}> = ({cue}) => {
  const frame = useCurrentFrame();
  const s = cue.style;
  const fade = Math.min(s.fade_frames ?? 0, (cue.end_frame - cue.start_frame) / 2);
  const progress = fade > 0 ? Math.min(1, frame / fade) : 1;
  const opacity = fade > 0 ? Math.min(progress, (cue.end_frame - cue.start_frame - frame) / fade) : 1;
  const scale = (s.entrance_scale ?? 1) + (1 - (s.entrance_scale ?? 1)) * progress;
  return <div style={{position: "absolute", left: s.left, top: s.top, width: s.width, height: s.height,
    display: "flex", alignItems: "center", justifyContent: "center",
    fontFamily: s.fontFamily, fontWeight: s.fontWeight, fontSize: s.fontSize, color: s.color,
    WebkitTextStroke: `${s.strokeWidth}px ${s.strokeColor}`, paintOrder: "stroke fill",
    textAlign: "center", whiteSpace: "pre-wrap", lineHeight: 1.05, opacity, transform: `scale(${scale})`}}>{cue.text}</div>;
};
export const ReferenceReplica: React.FC<ReferenceReplicaProps> = (props) => <AbsoluteFill style={{background: props.backgroundColor}}>
  {props.clips.map(clip => <Sequence key={clip.id} from={clip.from} durationInFrames={clip.duration}>
    <Picture clip={clip}/>
  </Sequence>)}
  {props.captions.map(cue => <Sequence key={cue.id} from={cue.start_frame} durationInFrames={cue.end_frame - cue.start_frame}>
    <Caption cue={cue}/>
  </Sequence>)}
  {props.audioSrc && <Audio src={src(props.audioSrc)}/>}
</AbsoluteFill>;
