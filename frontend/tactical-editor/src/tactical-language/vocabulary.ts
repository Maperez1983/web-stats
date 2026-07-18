import type { TacticalVerb } from './types';

export type TacticalVerbMeta = {
  verb: TacticalVerb;
  label: string;
  defaultDuration: number;
  defaultEasing: 'linear' | 'ease-in' | 'ease-out' | 'ease-in-out' | 'step';
  canMoveBall: boolean;
  canMoveActor: boolean;
  canRunInParallel: boolean;
};

export const MVP_VOCABULARY: TacticalVerbMeta[] = [
  {
    verb: 'PASS',
    label: 'Pase',
    defaultDuration: 0.9,
    defaultEasing: 'ease-in-out',
    canMoveBall: true,
    canMoveActor: false,
    canRunInParallel: true,
  },
  {
    verb: 'RECEIVE',
    label: 'Recepción',
    defaultDuration: 0.35,
    defaultEasing: 'ease-out',
    canMoveBall: false,
    canMoveActor: true,
    canRunInParallel: true,
  },
  {
    verb: 'CARRY',
    label: 'Conducción',
    defaultDuration: 1.8,
    defaultEasing: 'ease-in-out',
    canMoveBall: true,
    canMoveActor: true,
    canRunInParallel: true,
  },
  {
    verb: 'RUN',
    label: 'Carrera',
    defaultDuration: 1.4,
    defaultEasing: 'ease-in-out',
    canMoveBall: false,
    canMoveActor: true,
    canRunInParallel: true,
  },
  {
    verb: 'SUPPORT',
    label: 'Apoyo',
    defaultDuration: 1.2,
    defaultEasing: 'ease-out',
    canMoveBall: false,
    canMoveActor: true,
    canRunInParallel: true,
  },
  {
    verb: 'HOLD',
    label: 'Mantener',
    defaultDuration: 0.8,
    defaultEasing: 'linear',
    canMoveBall: false,
    canMoveActor: false,
    canRunInParallel: true,
  },
  {
    verb: 'CREATE_SPACE',
    label: 'Crear espacio',
    defaultDuration: 1.2,
    defaultEasing: 'ease-in-out',
    canMoveBall: false,
    canMoveActor: true,
    canRunInParallel: true,
  },
  {
    verb: 'OCCUPY_SPACE',
    label: 'Ocupar espacio',
    defaultDuration: 1.0,
    defaultEasing: 'ease-out',
    canMoveBall: false,
    canMoveActor: true,
    canRunInParallel: true,
  },
  {
    verb: 'BUILD_UP',
    label: 'Construcción',
    defaultDuration: 0,
    defaultEasing: 'linear',
    canMoveBall: false,
    canMoveActor: false,
    canRunInParallel: true,
  },
  {
    verb: 'PROGRESSION',
    label: 'Progresión',
    defaultDuration: 0,
    defaultEasing: 'linear',
    canMoveBall: false,
    canMoveActor: false,
    canRunInParallel: true,
  },
];

const META_MAP = new Map(MVP_VOCABULARY.map((item) => [item.verb, item]));

export function getVerbMeta(verb: TacticalVerb): TacticalVerbMeta {
  return META_MAP.get(verb) || MVP_VOCABULARY[0];
}
