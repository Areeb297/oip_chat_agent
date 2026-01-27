'use client';

import { useMemo, useState, useEffect, useCallback } from 'react';
import {
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
  LineChart,
  Line,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { Download, Maximize2, X } from 'lucide-react';
import { Button } from '@/components/ui/button';

// Chart configuration interface matching backend output
interface ChartConfig {
  type: 'bar' | 'line' | 'pie' | 'donut' | 'area' | 'gauge' | 'stackedBar' | 'groupedBar';
  title: string;
  description: string;
  figureLabel: string;
  data: Array<Record<string, unknown>>;
  xKey: string;
  series: Array<{
    key: string;
    label: string;
    color: string;
  }>;
  insights: string[];
  styling?: {
    showGrid?: boolean;
    showLegend?: boolean;
    showTooltip?: boolean;
    animate?: boolean;
  };
  innerRadius?: number;
  outerRadius?: number;
  showLabels?: boolean;
  labelType?: string;
  value?: number;
  maxValue?: number;
  target?: number;
  thresholds?: Array<{
    value: number;
    color: string;
    label: string;
  }>;
}

interface DynamicChartProps {
  config: ChartConfig;
}

// Custom tooltip component
const CustomTooltip = ({ active, payload, label }: { active?: boolean; payload?: Array<{ value: number; name: string; color: string }>; label?: string }) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-white p-3 rounded-lg shadow-lg border border-slate-200">
        <p className="font-medium text-slate-700">{label}</p>
        {payload.map((entry, index) => (
          <p key={index} style={{ color: entry.color }} className="text-sm">
            {entry.name}: {entry.value}
          </p>
        ))}
      </div>
    );
  }
  return null;
};

// Custom label for pie/donut charts
const renderCustomizedLabel = ({ cx, cy, midAngle, innerRadius, outerRadius, percent, name }: {
  cx?: number;
  cy?: number;
  midAngle?: number;
  innerRadius?: number;
  outerRadius?: number;
  percent?: number;
  name?: string;
}) => {
  const _cx = cx ?? 0;
  const _cy = cy ?? 0;
  const _midAngle = midAngle ?? 0;
  const _innerRadius = innerRadius ?? 0;
  const _outerRadius = outerRadius ?? 0;
  const _percent = percent ?? 0;

  const RADIAN = Math.PI / 180;
  const radius = _innerRadius + (_outerRadius - _innerRadius) * 1.4;
  const x = _cx + radius * Math.cos(-_midAngle * RADIAN);
  const y = _cy + radius * Math.sin(-_midAngle * RADIAN);

  if (_percent < 0.05) return null; // Don't show label for tiny slices

  return (
    <text
      x={x}
      y={y}
      fill="#374151"
      textAnchor={x > _cx ? 'start' : 'end'}
      dominantBaseline="central"
      className="text-xs font-medium"
    >
      {`${name ?? ''} (${(_percent * 100).toFixed(0)}%)`}
    </text>
  );
};

export function DynamicChart({ config }: DynamicChartProps) {
  const {
    type,
    title,
    description,
    figureLabel,
    data = [],
    xKey,
    series = [],
    insights = [],
    styling
  } = config || {};
  const [isFullscreen, setIsFullscreen] = useState(false);

  // Early return if no config or data
  if (!config || !type) {
    return <div className="p-4 text-slate-500">Invalid chart configuration</div>;
  }

  // Handle Escape key to close fullscreen
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (e.key === 'Escape' && isFullscreen) {
      setIsFullscreen(false);
    }
  }, [isFullscreen]);

  // Add keyboard listener and prevent body scroll when fullscreen
  useEffect(() => {
    if (isFullscreen) {
      document.addEventListener('keydown', handleKeyDown);
      document.body.style.overflow = 'hidden';
    }
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = '';
    };
  }, [isFullscreen, handleKeyDown]);

  // Get colors from data or series
  const colors = useMemo(() => {
    if (!data || data.length === 0) {
      return series.map((s) => s.color);
    }
    if (data[0]?.color) {
      return data.map((d) => d.color as string);
    }
    return series.map((s) => s.color);
  }, [data, series]);

  // Handle chart download
  const handleDownload = () => {
    const svg = document.querySelector('.recharts-wrapper svg');
    if (svg) {
      const svgData = new XMLSerializer().serializeToString(svg);
      const canvas = document.createElement('canvas');
      const ctx = canvas.getContext('2d');
      const img = new Image();

      img.onload = () => {
        canvas.width = img.width * 2;
        canvas.height = img.height * 2;
        if (ctx) {
          ctx.fillStyle = 'white';
          ctx.fillRect(0, 0, canvas.width, canvas.height);
          ctx.drawImage(img, 0, 0, canvas.width, canvas.height);

          const link = document.createElement('a');
          link.download = `${title.replace(/\s+/g, '_')}.png`;
          link.href = canvas.toDataURL('image/png');
          link.click();
        }
      };

      img.src = 'data:image/svg+xml;base64,' + btoa(unescape(encodeURIComponent(svgData)));
    }
  };

  // Render the appropriate chart type
  const renderChart = () => {
    const showLegend = styling?.showLegend ?? true;
    const animate = styling?.animate ?? true;

    switch (type) {
      case 'pie':
      case 'donut': {
        // For donut: use 60% of outer radius as inner radius (creates the hole)
        // For pie: innerRadius = 0 (no hole)
        const isDonut = type === 'donut' || config.innerRadius !== undefined && config.innerRadius > 0;
        const outerRadius = 90; // Fixed for consistent sizing
        const innerRadius = isDonut ? 55 : 0; // 55 creates a nice donut hole

        return (
          <PieChart>
            <Pie
              data={data}
              cx="50%"
              cy="50%"
              innerRadius={innerRadius}
              outerRadius={outerRadius}
              paddingAngle={2}
              dataKey={series[0]?.key || 'count'}
              nameKey={xKey}
              label={renderCustomizedLabel}
              labelLine={false}
              isAnimationActive={animate}
            >
              {data.map((entry, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={(entry.color as string) || colors[index % colors.length]}
                  stroke="white"
                  strokeWidth={2}
                />
              ))}
            </Pie>
            <Tooltip content={<CustomTooltip />} />
            {showLegend && <Legend />}
          </PieChart>
        );
      }

      case 'bar':
      case 'stackedBar':
      case 'groupedBar': {
        // Check if data items have individual colors (for status charts)
        const hasIndividualColors = data[0]?.color !== undefined;

        return (
          <BarChart data={data} barGap={type === 'groupedBar' ? 4 : 0}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis
              dataKey={xKey}
              tick={{ fill: '#64748b', fontSize: 12 }}
              axisLine={{ stroke: '#e2e8f0' }}
            />
            <YAxis
              tick={{ fill: '#64748b', fontSize: 12 }}
              axisLine={{ stroke: '#e2e8f0' }}
            />
            <Tooltip content={<CustomTooltip />} />
            {showLegend && (series.length > 1 || hasIndividualColors) && <Legend />}
            {series.map((s) => (
              <Bar
                key={s.key}
                dataKey={s.key}
                name={s.label}
                fill={hasIndividualColors ? undefined : s.color}
                stackId={type === 'stackedBar' ? 'stack' : undefined}
                radius={[4, 4, 0, 0]}
                isAnimationActive={animate}
              >
                {/* Add individual bar colors if data has color property */}
                {hasIndividualColors && data.map((entry, index) => (
                  <Cell
                    key={`cell-${index}`}
                    fill={(entry.color as string) || colors[index % colors.length]}
                  />
                ))}
              </Bar>
            ))}
          </BarChart>
        );
      }

      case 'line':
        return (
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis
              dataKey={xKey}
              tick={{ fill: '#64748b', fontSize: 12 }}
              axisLine={{ stroke: '#e2e8f0' }}
            />
            <YAxis
              tick={{ fill: '#64748b', fontSize: 12 }}
              axisLine={{ stroke: '#e2e8f0' }}
            />
            <Tooltip content={<CustomTooltip />} />
            {showLegend && series.length > 1 && <Legend />}
            {series.map((s) => (
              <Line
                key={s.key}
                type="monotone"
                dataKey={s.key}
                name={s.label}
                stroke={s.color}
                strokeWidth={2}
                dot={{ fill: s.color, strokeWidth: 2 }}
                activeDot={{ r: 6 }}
                isAnimationActive={animate}
              />
            ))}
          </LineChart>
        );

      case 'area':
        return (
          <AreaChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis
              dataKey={xKey}
              tick={{ fill: '#64748b', fontSize: 12 }}
              axisLine={{ stroke: '#e2e8f0' }}
            />
            <YAxis
              tick={{ fill: '#64748b', fontSize: 12 }}
              axisLine={{ stroke: '#e2e8f0' }}
            />
            <Tooltip content={<CustomTooltip />} />
            {showLegend && series.length > 1 && <Legend />}
            {series.map((s) => (
              <Area
                key={s.key}
                type="monotone"
                dataKey={s.key}
                name={s.label}
                stroke={s.color}
                fill={s.color}
                fillOpacity={0.3}
                isAnimationActive={animate}
              />
            ))}
          </AreaChart>
        );

      case 'gauge': {
        const value = config.value ?? 0;
        const maxValue = config.maxValue ?? 100;
        const percentage = (value / maxValue) * 100;

        // Determine color based on thresholds
        let gaugeColor = '#22c55e';
        if (config.thresholds) {
          for (const threshold of config.thresholds) {
            if (value <= threshold.value) {
              gaugeColor = threshold.color;
              break;
            }
          }
        }

        const gaugeData = [
          { name: 'Value', value: percentage },
          { name: 'Remaining', value: 100 - percentage },
        ];

        return (
          <PieChart>
            <Pie
              data={gaugeData}
              cx="50%"
              cy="50%"
              startAngle={180}
              endAngle={0}
              innerRadius={70}
              outerRadius={100}
              paddingAngle={0}
              dataKey="value"
              isAnimationActive={animate}
            >
              <Cell fill={gaugeColor} />
              <Cell fill="#e2e8f0" />
            </Pie>
            <text
              x="50%"
              y="45%"
              textAnchor="middle"
              dominantBaseline="middle"
              className="text-3xl font-bold"
              fill={gaugeColor}
            >
              {value.toFixed(1)}%
            </text>
            <text
              x="50%"
              y="60%"
              textAnchor="middle"
              dominantBaseline="middle"
              className="text-sm"
              fill="#64748b"
            >
              {config.target ? `Target: ${config.target}%` : ''}
            </text>
          </PieChart>
        );
      }

      default:
        return <div className="text-slate-500">Unsupported chart type: {type}</div>;
    }
  };

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden my-3">
      {/* Header */}
      <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between">
        <div>
          <h3 className="font-semibold text-slate-800">{title}</h3>
          <p className="text-xs text-slate-500">{figureLabel}</p>
        </div>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setIsFullscreen(true)}
            className="text-slate-500 hover:text-slate-700"
            title="View fullscreen"
          >
            <Maximize2 className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleDownload}
            className="text-slate-500 hover:text-slate-700"
          >
            <Download className="h-4 w-4 mr-1" />
            Download
          </Button>
        </div>
      </div>

      {/* Chart */}
      <div className="p-4">
        <ResponsiveContainer width="100%" height={280}>
          {renderChart()}
        </ResponsiveContainer>
      </div>

      {/* Description */}
      {description && (
        <div className="px-4 py-2 bg-slate-50 border-t border-slate-100">
          <p className="text-sm text-slate-600">{description}</p>
        </div>
      )}

      {/* Insights */}
      {insights && insights.length > 0 && (
        <div className="px-4 py-3 border-t border-slate-100">
          <p className="text-xs font-medium text-slate-500 uppercase mb-2">Key Insights</p>
          <ul className="space-y-1">
            {insights.map((insight, index) => (
              <li key={index} className="text-sm text-slate-700 flex items-start gap-2">
                <span className="text-blue-500 mt-1">•</span>
                {insight}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Fullscreen Modal */}
      {isFullscreen && (
        <div
          className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4"
          onClick={() => setIsFullscreen(false)}
        >
          <div
            className="bg-white rounded-2xl w-full max-w-5xl max-h-[90vh] overflow-auto shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Fullscreen Header */}
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between sticky top-0 bg-white z-10">
              <div>
                <h2 className="text-xl font-semibold text-slate-800">{title}</h2>
                <p className="text-sm text-slate-500">{figureLabel}</p>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleDownload}
                  className="text-slate-600"
                >
                  <Download className="h-4 w-4 mr-2" />
                  Download
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setIsFullscreen(false)}
                  className="text-slate-500 hover:text-slate-700"
                >
                  <X className="h-5 w-5" />
                </Button>
              </div>
            </div>

            {/* Fullscreen Chart */}
            <div className="p-6">
              <ResponsiveContainer width="100%" height={500}>
                {renderChart()}
              </ResponsiveContainer>
            </div>

            {/* Description */}
            {description && (
              <div className="px-6 py-4 bg-slate-50 border-t border-slate-100">
                <p className="text-slate-600">{description}</p>
              </div>
            )}

            {/* Insights in Fullscreen */}
            {insights && insights.length > 0 && (
              <div className="px-6 py-4 border-t border-slate-100">
                <p className="text-sm font-medium text-slate-500 uppercase mb-3">Key Insights</p>
                <ul className="space-y-2">
                  {insights.map((insight, index) => (
                    <li key={index} className="text-slate-700 flex items-start gap-2">
                      <span className="text-blue-500 mt-1">•</span>
                      {insight}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// Helper function to parse chart JSON from message content
export function parseChartFromContent(content: string): { chart: ChartConfig | null; textContent: string } {
  const chartStartMarker = '<!--CHART_START-->';
  const chartEndMarker = '<!--CHART_END-->';

  const startIndex = content.indexOf(chartStartMarker);
  const endIndex = content.indexOf(chartEndMarker);

  if (startIndex === -1 || endIndex === -1 || startIndex >= endIndex) {
    return { chart: null, textContent: content };
  }

  const jsonString = content.substring(startIndex + chartStartMarker.length, endIndex).trim();
  const textBefore = content.substring(0, startIndex).trim();
  const textAfter = content.substring(endIndex + chartEndMarker.length).trim();
  const textContent = `${textBefore}\n${textAfter}`.trim();

  try {
    const chart = JSON.parse(jsonString) as ChartConfig;
    return { chart, textContent };
  } catch (e) {
    console.error('Failed to parse chart JSON:', e);
    return { chart: null, textContent: content };
  }
}
