import React, { useState, useEffect } from "react";
import { api } from "../api/client";
import Plot from "react-plotly.js";

interface AnalyticsData {
  status: string;
  query_stats: {
    total_queries: number;
    successful_queries: number;
    failed_queries: number;
    success_rate: number;
  };
  performance: {
    avg_response_time_ms: number;
    total_execution_time_ms: number;
  };
  cache_performance: {
    cache_hits: number;
    llm_calls: number;
    cache_hit_rate: number;
    llm_calls_saved: number;
  };
  usage_patterns: {
    table_usage: Record<string, number>;
    hourly_queries: Record<string, number>;
    confidence_distribution: {
      high: number;
      medium: number;
      low: number;
    };
  };
  errors: {
    total_errors: number;
    error_types: Record<string, number>;
  };
  semantic_cache?: Record<string, any>;
  query_plan_cache?: Record<string, any>;
}

export const Analytics: React.FC = () => {
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchAnalytics = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await api.getAnalyticsDashboard();
      if (response.status === "ok") {
        setData(response);
      } else {
        setError(response.error || "Failed to load analytics");
      }
    } catch (err: any) {
      setError(err.message || "Failed to fetch analytics data");
    } finally {
      setLoading(false);
    }
  };

  const handleReset = async () => {
    if (window.confirm("Are you sure you want to reset all analytics data?")) {
      try {
        await api.resetAnalytics();
        await fetchAnalytics();
      } catch (err: any) {
        setError(err.message || "Failed to reset analytics");
      }
    }
  };

  useEffect(() => {
    fetchAnalytics();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-gray-400">Loading analytics...</div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-red-400">Error: {error || "Failed to load analytics"}</div>
      </div>
    );
  }

  const { query_stats, performance, cache_performance, usage_patterns, errors } = data;

  return (
    <div className="flex-1 flex flex-col overflow-auto">
      {/* Header */}
      <header className="h-16 border-b border-gray-800 flex items-center justify-between px-8">
        <h1 className="text-lg font-semibold tracking-tight flex items-center space-x-2">
          <span>📊</span>
          <span>Analytics Dashboard</span>
        </h1>
        <div className="flex items-center space-x-3">
          <button
            onClick={fetchAnalytics}
            className="glow-btn px-3 py-1.5 rounded-lg text-sm flex items-center space-x-2"
          >
            <span>🔄</span>
            <span>Refresh</span>
          </button>
          <button
            onClick={handleReset}
            className="glow-btn px-3 py-1.5 rounded-lg text-sm flex items-center space-x-2"
          >
            <span>🗑️</span>
            <span>Reset Data</span>
          </button>
        </div>
      </header>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-8 py-6 space-y-6">
        {/* Key Metrics */}
        <section>
          <h2 className="text-sm font-semibold text-gray-200 mb-4 flex items-center space-x-2">
            <span>📈</span>
            <span>Key Metrics</span>
          </h2>
          <div className="grid grid-cols-4 gap-4">
            <MetricCard
              label="Total Queries"
              value={query_stats.total_queries.toString()}
            />
            <MetricCard
              label="Success Rate"
              value={`${query_stats.success_rate.toFixed(1)}%`}
            />
            <MetricCard
              label="Avg Response Time"
              value={`${Math.round(performance.avg_response_time_ms)}ms`}
            />
            <MetricCard
              label="Cache Hit Rate"
              value={`${cache_performance.cache_hit_rate.toFixed(1)}%`}
            />
          </div>
        </section>

        <div className="border-t border-gray-800"></div>

        {/* Charts Row 1 */}
        <div className="grid grid-cols-2 gap-6">
          {/* Query Success vs Failure */}
          <ChartCard title="🎯 Query Success vs Failure">
            {(query_stats.successful_queries > 0 || query_stats.failed_queries > 0) ? (
              <Plot
                data={[
                  {
                    labels: ['Successful', 'Failed'],
                    values: [query_stats.successful_queries, query_stats.failed_queries],
                    type: 'pie',
                    hole: 0.4,
                    marker: {
                      colors: ['#28a745', '#dc3545']
                    }
                  }
                ]}
                layout={{
                  height: 300,
                  margin: { t: 20, b: 20, l: 20, r: 20 },
                  paper_bgcolor: 'rgba(0,0,0,0)',
                  plot_bgcolor: 'rgba(0,0,0,0)',
                  font: { color: '#9ca3af' },
                  showlegend: true,
                  legend: {
                    orientation: 'v',
                    x: 1,
                    y: 0.5
                  }
                }}
                config={{ displayModeBar: false }}
                style={{ width: '100%' }}
              />
            ) : (
              <div className="flex items-center justify-center h-64 text-gray-400 text-sm">
                ✅ Successful: {query_stats.successful_queries} | ❌ Failed: {query_stats.failed_queries}
              </div>
            )}
          </ChartCard>

          {/* Cache vs LLM Calls */}
          <ChartCard title="💾 Cache vs LLM Calls">
            {(cache_performance.cache_hits > 0 || cache_performance.llm_calls > 0) ? (
              <Plot
                data={[
                  {
                    labels: ['Cache Hits', 'LLM Calls'],
                    values: [cache_performance.cache_hits, cache_performance.llm_calls],
                    type: 'pie',
                    hole: 0.4,
                    marker: {
                      colors: ['#17a2b8', '#ffc107']
                    }
                  }
                ]}
                layout={{
                  height: 300,
                  margin: { t: 20, b: 20, l: 20, r: 20 },
                  paper_bgcolor: 'rgba(0,0,0,0)',
                  plot_bgcolor: 'rgba(0,0,0,0)',
                  font: { color: '#9ca3af' },
                  showlegend: true,
                  legend: {
                    orientation: 'v',
                    x: 1,
                    y: 0.5
                  }
                }}
                config={{ displayModeBar: false }}
                style={{ width: '100%' }}
              />
            ) : (
              <div className="flex items-center justify-center h-64 text-gray-400 text-sm">
                💾 Cache Hits: {cache_performance.cache_hits} | 🤖 LLM Calls: {cache_performance.llm_calls}
              </div>
            )}
          </ChartCard>
        </div>

        <div className="border-t border-gray-800"></div>

        {/* Charts Row 2 */}
        <div className="grid grid-cols-2 gap-6">
          {/* Table Usage */}
          <ChartCard title="📋 Table Usage">
            {Object.keys(usage_patterns.table_usage).length > 0 ? (
              <Plot
                data={[
                  {
                    x: Object.keys(usage_patterns.table_usage),
                    y: Object.values(usage_patterns.table_usage),
                    type: 'bar',
                    marker: {
                      color: Object.values(usage_patterns.table_usage),
                      colorscale: 'Blues'
                    }
                  }
                ]}
                layout={{
                  height: 300,
                  margin: { t: 20, b: 80, l: 40, r: 20 },
                  paper_bgcolor: 'rgba(0,0,0,0)',
                  plot_bgcolor: 'rgba(0,0,0,0)',
                  font: { color: '#9ca3af' },
                  xaxis: {
                    gridcolor: '#1f2937',
                    tickangle: -45
                  },
                  yaxis: {
                    gridcolor: '#1f2937'
                  }
                }}
                config={{ displayModeBar: false }}
                style={{ width: '100%' }}
              />
            ) : (
              <div className="flex items-center justify-center h-64 text-gray-400 text-sm">
                No table usage data yet
              </div>
            )}
          </ChartCard>

          {/* Confidence Distribution */}
          <ChartCard title="🎚️ Confidence Distribution">
            <Plot
              data={[
                {
                  x: ['High (≥80%)', 'Medium (50-79%)', 'Low (<50%)'],
                  y: [
                    usage_patterns.confidence_distribution.high,
                    usage_patterns.confidence_distribution.medium,
                    usage_patterns.confidence_distribution.low
                  ],
                  type: 'bar',
                  marker: {
                    color: ['#28a745', '#ffc107', '#dc3545']
                  }
                }
              ]}
              layout={{
                height: 300,
                margin: { t: 20, b: 60, l: 40, r: 20 },
                paper_bgcolor: 'rgba(0,0,0,0)',
                plot_bgcolor: 'rgba(0,0,0,0)',
                font: { color: '#9ca3af' },
                xaxis: {
                  gridcolor: '#1f2937'
                },
                yaxis: {
                  gridcolor: '#1f2937'
                }
              }}
              config={{ displayModeBar: false }}
              style={{ width: '100%' }}
            />
          </ChartCard>
        </div>

        {/* Hourly Trend */}
        {Object.keys(usage_patterns.hourly_queries).length > 0 && (
          <>
            <div className="border-t border-gray-800"></div>
            <ChartCard title="⏰ Hourly Query Trend">
              <Plot
                data={[
                  {
                    x: Object.keys(usage_patterns.hourly_queries).sort(),
                    y: Object.keys(usage_patterns.hourly_queries)
                      .sort()
                      .map((k) => usage_patterns.hourly_queries[k]),
                    type: 'scatter',
                    mode: 'lines+markers',
                    marker: { color: '#3b82f6' },
                    line: { color: '#3b82f6', width: 2 }
                  }
                ]}
                layout={{
                  height: 250,
                  margin: { t: 20, b: 60, l: 40, r: 20 },
                  paper_bgcolor: 'rgba(0,0,0,0)',
                  plot_bgcolor: 'rgba(0,0,0,0)',
                  font: { color: '#9ca3af' },
                  xaxis: {
                    gridcolor: '#1f2937',
                    tickangle: -45
                  },
                  yaxis: {
                    gridcolor: '#1f2937'
                  }
                }}
                config={{ displayModeBar: false }}
                style={{ width: '100%' }}
              />
            </ChartCard>
          </>
        )}

        {/* Error Analysis */}
        {errors.total_errors > 0 && (
          <>
            <div className="border-t border-gray-800"></div>
            <section>
              <h2 className="text-sm font-semibold text-gray-200 mb-4">⚠️ Error Analysis</h2>
              <div className="bg-[#0b1018] rounded-xl border border-gray-800 overflow-hidden">
                <table className="min-w-full text-xs">
                  <thead className="bg-[#0f1724] border-b border-gray-800 text-gray-300">
                    <tr>
                      <th className="text-left px-4 py-2 font-medium">Error Type</th>
                      <th className="text-right px-4 py-2 font-medium">Count</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(errors.error_types).map(([type, count]) => (
                      <tr key={type} className="border-b border-gray-800/60">
                        <td className="px-4 py-2 text-gray-200">{type}</td>
                        <td className="px-4 py-2 text-gray-200 text-right">{count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          </>
        )}

        {/* Cache Details */}
        <div className="border-t border-gray-800"></div>
        <CacheDetailsSection
          semanticCache={data.semantic_cache}
          queryPlanCache={data.query_plan_cache}
        />
      </div>
    </div>
  );
};

const MetricCard: React.FC<{ label: string; value: string }> = ({ label, value }) => (
  <div className="bg-[#0b1018] rounded-xl border border-gray-800 p-4">
    <div className="text-xs text-gray-400 mb-1">{label}</div>
    <div className="text-2xl font-semibold text-gray-100">{value}</div>
  </div>
);

const ChartCard: React.FC<{ title: string; children: React.ReactNode }> = ({
  title,
  children,
}) => (
  <div className="bg-[#0b1018] rounded-xl border border-gray-800 p-5">
    <h3 className="text-sm font-semibold text-gray-200 mb-4">{title}</h3>
    {children}
  </div>
);

const CacheDetailsSection: React.FC<{
  semanticCache?: Record<string, any>;
  queryPlanCache?: Record<string, any>;
}> = ({ semanticCache, queryPlanCache }) => {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <section>
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="glow-btn w-full flex items-center justify-between p-4 rounded-xl text-left"
      >
        <h2 className="text-sm font-semibold text-gray-200 flex items-center space-x-2">
          <span>🔧</span>
          <span>Cache Details</span>
        </h2>
        <span className="text-gray-400 text-lg">
          {isExpanded ? "▼" : "▶"}
        </span>
      </button>

      {isExpanded && (
        <div className="mt-4 grid grid-cols-2 gap-6">
          {/* Semantic Cache */}
          <div className="bg-[#0b1018] rounded-xl border border-gray-800 p-5">
            <h3 className="text-sm font-semibold text-gray-200 mb-3">Semantic Cache</h3>
            {semanticCache && Object.keys(semanticCache).length > 0 ? (
              <div className="bg-[#05070c] rounded-lg p-4 overflow-auto max-h-64">
                <pre className="text-xs text-gray-300 font-mono whitespace-pre-wrap">
                  {JSON.stringify(semanticCache, null, 2)}
                </pre>
              </div>
            ) : (
              <div className="text-xs text-gray-400 italic py-4">
                Semantic cache disabled or no data
              </div>
            )}
          </div>

          {/* Query Plan Cache */}
          <div className="bg-[#0b1018] rounded-xl border border-gray-800 p-5">
            <h3 className="text-sm font-semibold text-gray-200 mb-3">Query Plan Cache</h3>
            {queryPlanCache && Object.keys(queryPlanCache).length > 0 ? (
              <div className="bg-[#05070c] rounded-lg p-4 overflow-auto max-h-64">
                <pre className="text-xs text-gray-300 font-mono whitespace-pre-wrap">
                  {JSON.stringify(queryPlanCache, null, 2)}
                </pre>
              </div>
            ) : (
              <div className="text-xs text-gray-400 italic py-4">
                Query plan cache disabled or no data
              </div>
            )}
          </div>
        </div>
      )}
    </section>
  );
};

export default Analytics;
