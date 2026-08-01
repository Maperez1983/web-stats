export function addProtectedPitchBase({
  box,
  cylinder,
  plane,
  add,
  THREE,
  mats,
  halfW,
  halfH,
  pitchW,
  pitchH,
  apron,
  pitchBorderW,
  pitchBorderH,
  addRingSurface,
}) {
  addPitch();
  addApronAndBoards();

  function addPitch() {
    for (let i = 0; i < 14; i += 1) {
      const z = -halfH + (pitchH / 14) * (i + 0.5);
      box(`pitch_band_${i}`, i % 2 ? mats.grassDark : mats.grassLight, [0, 0.015, z], [pitchW, 0.03, pitchH / 14 + 0.04]);
    }

    const y = 0.07;
    box('touchline_north', mats.line, [0, y, halfH], [pitchW, 0.03, 0.14]);
    box('touchline_south', mats.line, [0, y, -halfH], [pitchW, 0.03, 0.14]);
    box('goal_line_west', mats.line, [-halfW, y, 0], [0.14, 0.03, pitchH]);
    box('goal_line_east', mats.line, [halfW, y, 0], [0.14, 0.03, pitchH]);
    box('halfway', mats.line, [0, y, 0], [0.14, 0.03, pitchH]);

    const circle = new THREE.Mesh(new THREE.TorusGeometry(9.15, 0.05, 8, 96), mats.line);
    circle.name = 'center_circle';
    circle.rotation.x = Math.PI / 2;
    circle.position.set(0, y + 0.004, 0);
    add(circle);
    cylinder('center_spot', mats.line, [0, y + 0.004, 0], 0.15, 0.15, 0.03);

    [-1, 1].forEach((sign) => {
      const x = sign * halfW;
      box(`penalty_area_top_${sign}`, mats.line, [x - sign * 8.25, y, 20.16], [16.5, 0.03, 0.12]);
      box(`penalty_area_bottom_${sign}`, mats.line, [x - sign * 8.25, y, -20.16], [16.5, 0.03, 0.12]);
      box(`penalty_area_inner_${sign}`, mats.line, [x - sign * 16.5, y, 0], [0.12, 0.03, 40.32]);
      box(`six_area_top_${sign}`, mats.line, [x - sign * 2.75, y, 9.16], [5.5, 0.03, 0.12]);
      box(`six_area_bottom_${sign}`, mats.line, [x - sign * 2.75, y, -9.16], [5.5, 0.03, 0.12]);
      box(`six_area_inner_${sign}`, mats.line, [x - sign * 5.5, y, 0], [0.12, 0.03, 18.32]);
      cylinder(`penalty_spot_${sign}`, mats.line, [x - sign * 11, y + 0.004, 0], 0.15, 0.15, 0.03);
    });
  }

  function addApronAndBoards() {
    box('apron_north', mats.apron, [0, 0.045, halfH + apron / 2], [pitchBorderW + 1.8, 0.08, apron]);
    box('apron_south', mats.apron, [0, 0.045, -(halfH + apron / 2)], [pitchBorderW + 1.8, 0.08, apron]);
    box('apron_east', mats.apron, [halfW + apron / 2, 0.045, 0], [apron, 0.08, pitchBorderH + 1.8]);
    box('apron_west', mats.apron, [-(halfW + apron / 2), 0.045, 0], [apron, 0.08, pitchBorderH + 1.8]);

    addRingSurface(
      'service_ring',
      mats.concreteDark,
      0.10,
      pitchBorderW / 2 + 1.2,
      pitchBorderH / 2 + 1.2,
      8.8,
      pitchBorderW / 2 + 0.25,
      pitchBorderH / 2 + 0.25,
      8.0,
    );

    const boards = [
      [0, halfH + 2.9, pitchW + 12, 0.22],
      [0, -(halfH + 2.9), pitchW + 12, 0.22],
      [halfW + 2.9, 0, 0.22, pitchH + 12],
      [-(halfW + 2.9), 0, 0.22, pitchH + 12],
    ];
    boards.forEach(([x, z, sx, sz], idx) => {
      box(`board_${idx}`, mats.board, [x, 0.84, z], [sx, 0.9, sz]);
    });
  }

}
