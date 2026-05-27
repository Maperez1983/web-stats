(function () {
  var canvas = document.getElementById('season-radar');
  if (!canvas || !canvas.getContext) return;
  var labels = String(canvas.dataset.labels || '').split('|').filter(Boolean);
  var values = String(canvas.dataset.values || '').split('|').map(function (value) {
    var parsed = parseFloat(value);
    return Number.isFinite(parsed) ? Math.max(0, Math.min(5, parsed)) : 0;
  });
  if (!labels.length) return;

  function categoryForAverage(value) {
    if (!Number.isFinite(value)) return 'Sin categoría';
    if (value >= 4.5) return 'Categoría superior / jugador diferencial';
    if (value >= 3.8) return 'Categoría alta';
    if (value >= 3.0) return 'Categoría actual consolidada';
    if (value >= 2.2) return 'Categoría actual con plan de mejora';
    return 'Categoría de desarrollo';
  }

  function draw() {
    var ctx = canvas.getContext('2d');
    var dpr = window.devicePixelRatio || 1;
    var cssSize = Math.max(220, Math.round(canvas.getBoundingClientRect().width || 280));
    canvas.width = cssSize * dpr;
    canvas.height = cssSize * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, cssSize, cssSize);

    var cx = cssSize / 2;
    var cy = cssSize / 2;
    var radius = Math.max(70, (cssSize / 2) - 42);
    var count = labels.length;
    var start = -Math.PI / 2;

    ctx.lineWidth = 1;
    ctx.font = '12px Avenir Next, Segoe UI, sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';

    for (var level = 1; level <= 5; level += 1) {
      ctx.beginPath();
      for (var i = 0; i < count; i += 1) {
        var angle = start + (Math.PI * 2 * i / count);
        var r = radius * level / 5;
        var x = cx + Math.cos(angle) * r;
        var y = cy + Math.sin(angle) * r;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.closePath();
      ctx.strokeStyle = level === 5 ? 'rgba(255,255,255,0.26)' : 'rgba(255,255,255,0.12)';
      ctx.stroke();
    }

    for (var axis = 0; axis < count; axis += 1) {
      var axisAngle = start + (Math.PI * 2 * axis / count);
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.lineTo(cx + Math.cos(axisAngle) * radius, cy + Math.sin(axisAngle) * radius);
      ctx.strokeStyle = 'rgba(255,255,255,0.13)';
      ctx.stroke();

      var lx = cx + Math.cos(axisAngle) * (radius + 24);
      var ly = cy + Math.sin(axisAngle) * (radius + 24);
      ctx.fillStyle = 'rgba(238,242,255,0.88)';
      ctx.fillText(labels[axis], lx, ly);
    }

    ctx.beginPath();
    values.forEach(function (value, index) {
      var angle = start + (Math.PI * 2 * index / count);
      var r = radius * value / 5;
      var x = cx + Math.cos(angle) * r;
      var y = cy + Math.sin(angle) * r;
      if (index === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.closePath();
    ctx.fillStyle = 'rgba(244,180,0,0.22)';
    ctx.strokeStyle = 'rgba(244,180,0,0.92)';
    ctx.lineWidth = 2;
    ctx.fill();
    ctx.stroke();

    values.forEach(function (value, index) {
      var angle = start + (Math.PI * 2 * index / count);
      var r = radius * value / 5;
      var x = cx + Math.cos(angle) * r;
      var y = cy + Math.sin(angle) * r;
      ctx.beginPath();
      ctx.arc(x, y, 4, 0, Math.PI * 2);
      ctx.fillStyle = '#f4b400';
      ctx.fill();
    });
  }

  function recalcFromInputs() {
    var groupNodes = Array.prototype.slice.call(document.querySelectorAll('[data-rating-group]'));
    var allValues = [];
    values = groupNodes.map(function (groupNode, index) {
      var groupValues = Array.prototype.slice.call(groupNode.querySelectorAll('[data-rating-input]')).map(function (select) {
        var parsed = parseInt(select.value, 10);
        return Number.isFinite(parsed) ? Math.max(0, Math.min(5, parsed)) : null;
      }).filter(function (value) {
        return value !== null;
      });
      Array.prototype.push.apply(allValues, groupValues);
      var avg = groupValues.length ? groupValues.reduce(function (acc, value) { return acc + value; }, 0) / groupValues.length : 0;
      var avgNode = groupNode.querySelector('[data-group-average]');
      if (avgNode) avgNode.textContent = groupValues.length ? avg.toFixed(2) : '-';
      if (!labels[index]) labels[index] = String(groupNode.dataset.ratingGroup || '');
      return avg;
    });
    var overallNode = document.querySelector('[data-rating-overall]');
    var categoryNode = document.querySelector('[data-rating-category]');
    var overall = allValues.length ? allValues.reduce(function (acc, value) { return acc + value; }, 0) / allValues.length : NaN;
    if (overallNode) overallNode.textContent = Number.isFinite(overall) ? overall.toFixed(2) : '-';
    if (categoryNode) categoryNode.textContent = categoryForAverage(overall);
    draw();
  }

  draw();
  Array.prototype.slice.call(document.querySelectorAll('[data-rating-input]')).forEach(function (select) {
    select.addEventListener('change', recalcFromInputs);
  });
  window.addEventListener('resize', draw);
}());
