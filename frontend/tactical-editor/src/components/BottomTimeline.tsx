import { useEffect, useMemo, useRef, useState } from 'react';
import { advanceAnimationTime, createAnimationPlaybackState, type AnimationPlaybackState } from '../editor/animation/AnimationPlayer';
import { resolveAnimationDuration } from '../editor/animation/AnimationEngine';
import { toggleAnimationSelection } from '../editor/animation/AnimationSelection';
import type { TacticalScene } from '../editor/core/sceneSchema';
import { useEditorStore } from '../store/editorStore';

type TimelineDragState = {
  ids: string[];
  startTimes: Map<string, number>;
  startX: number;
  snapSeconds: number;
};

const TIMELINE_SECONDS_PER_PIXEL = 120;
const SPEED_OPTIONS = [0.25, 0.5, 1, 2, 4] as const;

function getSortedKeyframes(sceneKeyframes: TacticalScene['timeline']['keyframes']) {
  return [...sceneKeyframes].sort((left, right) => left.time - right.time);
}

export function BottomTimeline() {
  const scene = useEditorStore((state) => state.scene);
  const selectedIds = useEditorStore((state) => state.selectedIds);
  const setTimelineTime = useEditorStore((state) => state.setTimelineTime);
  const setTimelineDuration = useEditorStore((state) => state.setTimelineDuration);
  const addTimelineKeyframe = useEditorStore((state) => state.addTimelineKeyframe);
  const removeTimelineKeyframe = useEditorStore((state) => state.removeTimelineKeyframe);
  const moveTimelineKeyframe = useEditorStore((state) => state.moveTimelineKeyframe);
  const duplicateTimelineKeyframes = useEditorStore((state) => state.duplicateTimelineKeyframes);
  const beginTransaction = useEditorStore((state) => state.beginTransaction);
  const commitTransaction = useEditorStore((state) => state.commitTransaction);
  const recreationToken = useEditorStore((state) => state.tacticalRecreationToken);
  const [playback, setPlayback] = useState<AnimationPlaybackState>(() => createAnimationPlaybackState());
  const [selectedKeyframeIds, setSelectedKeyframeIds] = useState<string[]>([]);
  const [clipboardIds, setClipboardIds] = useState<string[]>([]);
  const [dragState, setDragState] = useState<TimelineDragState | null>(null);
  const [dragPreviewDelta, setDragPreviewDelta] = useState(0);
  const dragRef = useRef<TimelineDragState | null>(null);
  const lastFrameTimeRef = useRef<number | null>(null);
  const lastRecreationTokenRef = useRef<number>(recreationToken);

  const keyframes = scene?.timeline?.keyframes || [];
  const currentTime = scene?.timeline?.currentTime || 0;
  const duration = scene ? resolveAnimationDuration(scene) : 0;
  const sortedKeyframes = useMemo(() => getSortedKeyframes(keyframes), [keyframes]);
  const playbackDuration = Math.max(duration, sortedKeyframes[sortedKeyframes.length - 1]?.time || 0, 1);
  const timelineZoom = playback.timelineZoom;
  const timeToPx = (time: number) => time * TIMELINE_SECONDS_PER_PIXEL * timelineZoom;
  const pxToTime = (px: number) => px / (TIMELINE_SECONDS_PER_PIXEL * timelineZoom);
  const selectedCount = selectedKeyframeIds.length;
  const hasSelection = selectedIds.length > 0;

  useEffect(() => {
    if (!scene) {
      return;
    }
    const sceneTimeline = scene.timeline ?? { duration: 0, currentTime: 0, keyframes: [], tracks: [], sequences: [], currentSequenceId: null };
    const nextDuration = Math.max(playbackDuration, sceneTimeline.duration);
    if (sceneTimeline.duration !== nextDuration) {
      setTimelineDuration(nextDuration);
    }
  }, [playbackDuration, scene, setTimelineDuration]);

  useEffect(() => {
    if (recreationToken === lastRecreationTokenRef.current) {
      return;
    }
    lastRecreationTokenRef.current = recreationToken;
    setTimelineTime(0);
    setPlayback((state) => ({ ...state, playing: true, loop: true }));
  }, [recreationToken, setTimelineTime]);

  useEffect(() => {
    if (!playback.playing || !useEditorStore.getState().scene) {
      lastFrameTimeRef.current = null;
      return undefined;
    }
    let animationFrame = 0;
    const tick = (now: number) => {
      const last = lastFrameTimeRef.current ?? now;
      lastFrameTimeRef.current = now;
      const delta = now - last;
      const currentTime = useEditorStore.getState().scene?.timeline?.currentTime || 0;
      const next = advanceAnimationTime(currentTime, delta, playback, playbackDuration);
      setTimelineTime(next.time);
      if (!playback.loop && next.time >= playbackDuration) {
        setPlayback((state) => ({ ...state, playing: false }));
        lastFrameTimeRef.current = null;
        return;
      }
      animationFrame = window.requestAnimationFrame(tick);
    };
    animationFrame = window.requestAnimationFrame(tick);
    return () => {
      window.cancelAnimationFrame(animationFrame);
      lastFrameTimeRef.current = null;
    };
  }, [playback.playing, playback.loop, playback.speed, playbackDuration, setTimelineTime]);

  useEffect(() => {
    if (!dragState) {
      return undefined;
    }
    const handleMove = (event: PointerEvent) => {
      const deltaSeconds = pxToTime(event.clientX - dragState.startX);
      const snapped = Math.round(deltaSeconds / dragState.snapSeconds) * dragState.snapSeconds;
      setDragPreviewDelta(snapped);
    };
    const handleUp = () => {
      const state = dragRef.current;
      if (state) {
        beginTransaction();
        state.ids.forEach((id) => {
          const baseTime = state.startTimes.get(id) ?? 0;
          moveTimelineKeyframe(id, Math.max(0, baseTime + dragPreviewDelta));
        });
        commitTransaction();
      }
      dragRef.current = null;
      setDragState(null);
      setDragPreviewDelta(0);
      window.removeEventListener('pointermove', handleMove);
    };
    window.addEventListener('pointermove', handleMove);
    window.addEventListener('pointerup', handleUp, { once: true });
    window.addEventListener('pointercancel', handleUp, { once: true });
    return () => {
      window.removeEventListener('pointermove', handleMove);
      window.removeEventListener('pointerup', handleUp);
      window.removeEventListener('pointercancel', handleUp);
    };
  }, [beginTransaction, commitTransaction, dragPreviewDelta, dragState, moveTimelineKeyframe, pxToTime]);

  const visibleCards = useMemo(
    () =>
      sortedKeyframes.map((card, index) => ({
        ...card,
        left: timeToPx(card.time),
        lane: index % 3,
      })),
    [sortedKeyframes, timelineZoom]
  );

  const currentMarkerLeft = timeToPx(currentTime);

  const beginDrag = (ids: string[], clientX: number) => {
    const startTimes = new Map<string, number>();
    ids.forEach((id) => {
      const entry = sortedKeyframes.find((card) => card.id === id);
      if (entry) {
        startTimes.set(id, entry.time);
      }
    });
    const state = {
      ids,
      startTimes,
      startX: clientX,
      snapSeconds: Math.max(0.1, 1 / (timelineZoom * 4)),
    };
    dragRef.current = state;
    setDragState(state);
    setDragPreviewDelta(0);
  };

  const commitSelectionDuplicate = () => {
    if (!selectedKeyframeIds.length) {
      return;
    }
    duplicateTimelineKeyframes(selectedKeyframeIds, 0.5);
  };

  const commitSelectionCopy = () => {
    setClipboardIds([...selectedKeyframeIds]);
  };

  const commitSelectionPaste = () => {
    if (!clipboardIds.length) {
      return;
    }
    duplicateTimelineKeyframes(clipboardIds, 0.5);
    setSelectedKeyframeIds([...clipboardIds]);
  };

  const deleteSelection = () => {
    if (!selectedKeyframeIds.length) {
      return;
    }
    const ids = selectedKeyframeIds;
    beginTransaction();
    ids.forEach((id) => removeTimelineKeyframe(id));
    commitTransaction();
    setSelectedKeyframeIds([]);
  };

  const visibleKeyframeCount = sortedKeyframes.length;
  const trackCount = scene?.timeline?.tracks?.length || 0;
  const rulerWidth = Math.max(720, timeToPx(playbackDuration) + 120);

  return (
    <section className="te-panel te-timeline">
      <div className="te-panel-head">
        <div>
          <h2>Timeline</h2>
          <span>
            {visibleKeyframeCount} keyframes · {trackCount} tracks · {currentTime.toFixed(1)}s / {playbackDuration.toFixed(1)}s
          </span>
        </div>
        <div className="te-timeline-status">
          <span>{playback.playing ? 'Reproduciendo' : 'Pausado'}</span>
          <span>{playback.loop ? 'Loop activo' : 'Loop apagado'}</span>
        </div>
      </div>
      <div className="te-action-row wrap te-timeline-toolbar">
        <button
          type="button"
          data-testid="animation-play"
          aria-label="Reproducir animación"
          disabled={playback.playing}
          onClick={() => setPlayback((state) => ({ ...state, playing: true }))}
        >
          Play
        </button>
        <button
          type="button"
          data-testid="animation-pause"
          aria-label="Pausar animación"
          disabled={!playback.playing}
          onClick={() => setPlayback((state) => ({ ...state, playing: false }))}
        >
          Pausa
        </button>
        <button
          type="button"
          data-testid="animation-stop"
          aria-label="Detener animación"
          onClick={() => {
            setPlayback((state) => ({ ...state, playing: false }));
            setTimelineTime(0);
          }}
        >
          Stop
        </button>
        <button type="button" className={playback.loop ? 'is-active' : ''} onClick={() => setPlayback((state) => ({ ...state, loop: !state.loop }))}>
          Loop
        </button>
        <div className="te-speed-group" aria-label="Velocidad de reproducción">
          {SPEED_OPTIONS.map((speed) => (
            <button
              key={speed}
              type="button"
              className={playback.speed === speed ? 'is-active' : ''}
              onClick={() => setPlayback((state) => ({ ...state, speed }))}
            >
              {speed}x
            </button>
          ))}
        </div>
        <button type="button" data-testid="animation-go-start" aria-label="Ir al inicio" onClick={() => setTimelineTime(0)}>
          Inicio
        </button>
        <button
          type="button"
          data-testid="animation-go-end"
          aria-label="Ir al final"
          onClick={() => setTimelineTime(playbackDuration)}
        >
          Final
        </button>
        <button type="button" aria-label="Añadir keyframe" disabled={!hasSelection} onClick={() => addTimelineKeyframe()}>
          Añadir keyframe
        </button>
        <button type="button" onClick={commitSelectionDuplicate}>
          Duplicar
        </button>
        <button type="button" onClick={commitSelectionCopy}>
          Copiar
        </button>
        <button type="button" onClick={commitSelectionPaste}>
          Pegar
        </button>
        <button type="button" onClick={deleteSelection}>
          Eliminar
        </button>
      </div>
      <div className="te-timeline-metrics">
        <label>
          Duración
          <input
            type="number"
            min="1"
            step="0.5"
            value={playbackDuration.toFixed(1)}
            onChange={(event) => setTimelineDuration(Number(event.target.value))}
          />
        </label>
        <label>
          Zoom
          <input
            type="range"
            data-testid="timeline-zoom"
            min="0.5"
            max="2.5"
            step="0.1"
            value={playback.timelineZoom}
            onChange={(event) =>
              setPlayback((state) => ({ ...state, timelineZoom: Number(event.target.value) }))
            }
          />
        </label>
        <label>
          Tiempo
          <input
            type="range"
            data-testid="timeline-time"
            min="0"
            max={Math.max(playbackDuration, 1)}
            step="0.1"
            value={currentTime}
            onChange={(event) => setTimelineTime(Number(event.target.value))}
          />
        </label>
      </div>
      <div className="te-timeline-scroll">
        <div className="te-timeline-track" style={{ width: `${rulerWidth}px` }}>
          {Array.from({ length: Math.max(1, Math.ceil(playbackDuration)) + 1 }).map((_, index) => {
            const time = index;
            return (
              <div
                key={`tick-${time}`}
                className="te-timeline-tick"
                style={{ left: `${timeToPx(time)}px` }}
                aria-hidden="true"
              >
                <span>{time}s</span>
              </div>
            );
          })}
          <button
            type="button"
            className="te-timeline-marker"
            style={{ left: `${currentMarkerLeft}px` }}
            aria-label="Marcador temporal actual"
            onClick={() => setTimelineTime(currentTime)}
          />
          {visibleCards.map((card) => {
            const selected = selectedKeyframeIds.includes(card.id);
            const previewTime = dragState && dragState.ids.includes(card.id)
              ? Math.max(0, (dragState.startTimes.get(card.id) || card.time) + dragPreviewDelta)
              : card.time;
            return (
              <button
                key={card.id}
                type="button"
                className={`te-timeline-card ${selected ? 'is-selected' : ''} ${dragState?.ids.includes(card.id) ? 'is-dragging' : ''}`}
                style={{
                  left: `${timeToPx(previewTime)}px`,
                  top: `${28 + card.lane * 78}px`,
                }}
                onPointerDown={(event) => {
                  event.preventDefault();
                  const additive = event.shiftKey || event.metaKey || event.ctrlKey;
                  const nextSelection = additive
                    ? toggleAnimationSelection(selectedKeyframeIds, card.id, true)
                    : [card.id];
                  setSelectedKeyframeIds(nextSelection);
                  beginDrag(nextSelection, event.clientX);
                }}
              >
                <strong>{String(card.label || `KF ${card.time.toFixed(1)}`)}</strong>
                <span>{card.time.toFixed(1)}s · {card.objectIds.length} objetos</span>
              </button>
            );
          })}
        </div>
      </div>
      <div className="te-timeline-ruler">
        <div className="te-tick">
          <strong>Keyframes</strong>
          <span>Selecciona, duplica y arrastra keyframes con snap temporal.</span>
        </div>
        <div className="te-tick">
          <strong>Escena animada</strong>
          <span>La reproducción evalúa la escena sin mutar el documento original.</span>
        </div>
        <div className="te-tick">
          <strong>Selección</strong>
          <span>{selectedCount ? `${selectedCount} keyframes seleccionados` : 'Ningún keyframe seleccionado'}</span>
        </div>
      </div>
    </section>
  );
}
