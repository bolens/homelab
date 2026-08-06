/*
 * ECharts draws text, grids, legends, and tooltips into a canvas, outside the
 * reach of CSS. Default unthemed charts to ECharts' bundled dark theme while
 * preserving any explicit theme selected by an upstream page.
 */
(function () {
  if (!window.echarts || typeof window.echarts.init !== "function") {
    return;
  }

  var originalInit = window.echarts.init;
  window.echarts.init = function (element, theme, options) {
    return originalInit.call(window.echarts, element, theme || "dark", options);
  };
}());
