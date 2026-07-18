import { createObject } from '../../editor/objects/ObjectFactory';
import { createDefaultScene } from '../../editor/core/sceneSchema';
import type { TacticalScene } from '../../editor/core/sceneSchema';

export function createBuildUpFromGoalkeeperFixture(): TacticalScene {
  const scene = createDefaultScene('mvp-build-up', 'Salida de balón MVP', 1050, 680);
  scene.objects.push(
    createObject('goalkeeper-home', { x: 120, y: 300, assetId: 'player.home.front' }),
    createObject('player-home', { x: 330, y: 230, assetId: 'player.home.back' }),
    createObject('player-home', { x: 330, y: 390, assetId: 'player.home.back' }),
    createObject('player-home', { x: 520, y: 335, assetId: 'player.home.front' }),
    createObject('player-home', { x: 640, y: 230, assetId: 'player.home.side' }),
    createObject('ball', { x: 150, y: 310, assetId: 'ball.standard' }),
    createObject('arrow-pass', { x: 155, y: 310 }),
    createObject('arrow-run', { x: 640, y: 230 }),
    createObject('arrow-pass', { x: 370, y: 250 }),
    createObject('zone-rect', { x: 780, y: 180 }),
    createObject('cone', { x: 790, y: 180 }),
    createObject('cone', { x: 860, y: 180 }),
    createObject('cone', { x: 790, y: 260 }),
    createObject('cone', { x: 860, y: 260 })
  );
  scene.objects[0].data.label = 'Portero';
  scene.objects[1].data.label = 'Central derecho';
  scene.objects[2].data.label = 'Central izquierdo';
  scene.objects[3].data.label = 'Mediocentro';
  scene.objects[4].data.label = 'Lateral derecho';
  scene.objects[5].data.label = 'Balón';
  scene.objects[9].data.label = 'Zona objetivo';
  scene.objects[6].data.label = 'Pase 1';
  scene.objects[7].data.label = 'Carrera';
  scene.objects[8].data.label = 'Pase 2';
  return scene;
}
