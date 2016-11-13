(function ($) {
	"use strict";

	var options = {};

  function floorInBase(n, base) {
    return base * Math.floor(n / base);
  }

	function init(plot) {
		plot.hooks.processDatapoints.push(function (plot) {
			$.each(plot.getAxes(), function(axisName, axis) {
				var opts = axis.options;

				if (opts.mode === 'seconds' || opts.mode === 'second') {

          // Add default tickGenerator so that tickFormatter is not overwritten by the default one
          axis.tickGenerator = function (axis) {
            var ticks = [],
                start = floorInBase(axis.min, axis.tickSize),
                i = 0,
                v = Number.NaN,
                prev;

            do {
                prev = v;
                v = start + i * axis.tickSize;
                ticks.push(v);
                ++i;
            } while (v < axis.max && v != prev);

            return ticks;
          };

					axis.tickFormatter = function(size, axis) {
						var ext, steps = 0;

						while (size && Math.abs(size) < 1) {
							steps++;
							size *= 1000;
						}

						switch (steps) {
							case 0: ext = ' s';  break;
							case 1: ext = " ms"; break;
							case 2: ext = " µs"; break;
							case 3: ext = " ns"; break;
							case 4: ext = " ps"; break;
							case 5: ext = " fs"; break;
							case 6: ext = " as"; break;
							case 7: ext = " zs"; break;
							case 8: ext = " ys"; break;
						}

						return (size.toFixed(2) + ext);
					};
				}

			});
		});
	}  // init()

	$.plot.plugins.push({
		init: init,
		options: options,
		name: 'second',
		version: '0.1'
	});
})(jQuery);
