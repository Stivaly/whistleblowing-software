import * as echarts from 'echarts/core';
import { BarChart, LineChart, PieChart, HeatmapChart } from 'echarts/charts';
import { GridComponent, TooltipComponent, LegendComponent, MarkLineComponent, VisualMapComponent, AriaComponent, GraphicComponent } from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
echarts.use([BarChart, LineChart, PieChart, HeatmapChart, GridComponent, TooltipComponent, LegendComponent, MarkLineComponent, VisualMapComponent, AriaComponent, GraphicComponent, CanvasRenderer]);
window.echarts = echarts;
