(function ($) {
	"use strict";

	var options = {};

	//Round to nearby lower multiple of base
	function floorInBase(n, base) {
		return base * Math.floor(n / base);
	}

	function init(plot) {
		plot.hooks.processDatapoints.push(function (plot) {
			$.each(plot.getAxes(), function(axisName, axis) {
				var opts = axis.options;
				if (opts.mode === "bit" || opts.mode === "bitRate") {
					//Enforce maximum tick Decimals
					axis.tickDecimals = 2;

					axis.tickGenerator = function (axis) {
						var returnTicks = [],
							tickSize = 2,
							delta = axis.delta,
							steps = 0,
							tickMin = 0,
							tickVal,
							tickCount = 0;

						//Set the reference for the formatter
						if (opts.mode === "bitRate") {
							axis.rate = true;
						}

						//Count the steps
						while (Math.abs(delta) >= 1000) {
							steps++;
							delta /= 1000;
						}

						//Set the tick size relative to the remaining delta
						while (tickSize <= 1000) {
							if (delta <= tickSize) {
								break;
							}
							tickSize *= 2;
						}

						//Tell flot the tickSize we've calculated
						if (typeof opts.minTickSize !== "undefined" && tickSize < opts.minTickSize) {
							axis.tickSize = opts.minTickSize;
						} else {
							axis.tickSize = tickSize * Math.pow(1000,steps);
						}

						//Calculate the new ticks
						tickMin = floorInBase(axis.min, axis.tickSize);
						do {
							tickVal = tickMin + (tickCount++) * axis.tickSize;
							returnTicks.push(tickVal);
						} while (tickVal < axis.max);

						return returnTicks;
					};

					axis.tickFormatter = function(size, axis) {
						var ext, steps = 0;

						while (Math.abs(size) >= 1000) {
							steps++;
							size /= 1000;
						}

						switch (steps) {
							case 0: ext = " bit";  break;
							case 1: ext = " kbit"; break;
							case 2: ext = " Mbit"; break;
							case 3: ext = " Gbit"; break;
							case 4: ext = " Tbit"; break;
							case 5: ext = " Pbit"; break;
							case 6: ext = " Ebit"; break;
							case 7: ext = " Zbit"; break;
							case 8: ext = " Ybit"; break;
						}

						if (typeof axis.rate !== "undefined") {
							ext += "/s";
						}

						return (size.toFixed(2) + ext);
					};
				}
			});
		});
	}

	$.plot.plugins.push({
		init: init,
		options: options,
		name: "bit",
		version: "0.1"
	});
})(jQuery);
