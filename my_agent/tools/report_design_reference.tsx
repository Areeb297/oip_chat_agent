import "./report.css";

export function Report() {
  const engineers = [
    { name: "Rehan Shehbaz", total: 56, completed: 1, rate: "1.8%", color: "#3B82F6" },
    { name: "Ranju Kallil", total: 49, completed: 0, rate: "0.0%", color: "#8B5CF6" },
    { name: "Kashif Raza", total: 37, completed: 0, rate: "0.0%", color: "#06B6D4" },
    { name: "Muthaleeb Kaniyankandi", total: 32, completed: 0, rate: "0.0%", color: "#10B981" },
    { name: "Faisal Saleh", total: 4, completed: 0, rate: "0.0%", color: "#F59E0B" },
    { name: "Faisal Bashir", total: 1, completed: 0, rate: "0.0%", color: "#EF4444" },
  ];

  const supervisors = [
    { name: "Anoop Sasidharan", region: "Eastern Province, Al Jawf", total: 325 },
    { name: "Ahmed D", region: "Makkah", total: 206 },
    { name: "Raja Yousuf", region: "Riyadh", total: 190 },
    { name: "Mudassar Hameed", region: "Madinah, Tabuk, Hail, Qassim", total: 130 },
    { name: "Neil Paz", region: "Jizan, Asir, Najran, Al Bahah", total: 54 },
  ];

  const basePath = import.meta.env.BASE_URL;

  return (
    <div className="report-root">

      <div className="page">
        <div className="page-header-band">
          <div className="header-left">
            <img src={`${basePath}images/ebttikar-logo.png`} alt="Ebttikar OIP" className="header-logo" />
            <div className="header-title-block">
              <h1 className="report-title">Saudi Awwal Bank</h1>
              <p className="report-subtitle">Project Performance Report</p>
            </div>
          </div>
          <div className="header-right">
            <div className="header-meta-item">
              <span className="meta-label">Date</span>
              <span className="meta-value">11 March 2026</span>
            </div>
            <div className="header-meta-item">
              <span className="meta-label">Prepared by</span>
              <span className="meta-value">Ebttikar OIP</span>
            </div>
            <div className="header-meta-item">
              <span className="meta-label">Classification</span>
              <span className="meta-value confidential">Confidential</span>
            </div>
          </div>
        </div>
        <div className="accent-bar" />

        <div className="page-body">
          <div className="kpi-row">
            {[
              { label: "Total Tickets", value: "369", color: "#2746E3", bg: "#EEF2FF", icon: "\uD83C\uDFAB" },
              { label: "Open Tickets", value: "368", color: "#D97706", bg: "#FEF3C7", icon: "\uD83D\uDCC2", sub: "99.7%" },
              { label: "Completed", value: "1", color: "#059669", bg: "#D1FAE5", icon: "\u2705", sub: "0.3%" },
              { label: "SLA Breached", value: "368", color: "#DC2626", bg: "#FEE2E2", icon: "\u26A0\uFE0F", sub: "99.7%" },
              { label: "PM Tickets", value: "1,084", color: "#7C3AED", bg: "#F3E8FF", icon: "\uD83D\uDD27", sub: "100%" },
              { label: "Engineers", value: "11/26", color: "#0891B2", bg: "#E0F2FE", icon: "\uD83D\uDC77", sub: "active" },
            ].map((k) => (
              <div key={k.label} className="kpi-card" style={{ background: k.bg }}>
                <div className="kpi-value" style={{ color: k.color }}>{k.value}</div>
                <div className="kpi-label">{k.label}</div>
                {k.sub && <div className="kpi-sub">{k.sub}</div>}
              </div>
            ))}
          </div>

          <div className="two-col">
            <div className="col-left">
              <div className="section-block">
                <h2 className="section-heading"><span className="sec-num">01</span> Executive Summary</h2>
                <p className="body-text">
                  The Saudi Awwal Bank project manages <strong>369 tickets</strong>, of which <strong>368 remain open</strong> and SLA-breached, with only <strong>1 completed</strong>. The team of <strong>26 engineers</strong> (11 active) handles <strong>1,084 PM tickets</strong> at a 0.09% completion rate. Zero inventory transactions have been recorded.
                </p>
              </div>

              <div className="section-block">
                <h2 className="section-heading"><span className="sec-num">02</span> Key Insights</h2>
                <div className="insight-list">
                  <div className="insight critical">
                    <span className="ins-dot" style={{ background: "#EF4444" }} />
                    <span>368/369 tickets open &amp; SLA-breached — <strong>99.7% breach rate</strong></span>
                  </div>
                  <div className="insight critical">
                    <span className="ins-dot" style={{ background: "#EF4444" }} />
                    <span>Completion rate stands at only <strong>0.09%</strong> across 1,084 PM tickets</span>
                  </div>
                  <div className="insight info">
                    <span className="ins-dot" style={{ background: "#3B82F6" }} />
                    <span>PM tickets represent <strong>100%</strong> of total ticket volume</span>
                  </div>
                  <div className="insight info">
                    <span className="ins-dot" style={{ background: "#3B82F6" }} />
                    <span>Only <strong>11 of 26 engineers</strong> are currently active</span>
                  </div>
                  <div className="insight info">
                    <span className="ins-dot" style={{ background: "#3B82F6" }} />
                    <span>Zero inventory transactions recorded across all sites</span>
                  </div>
                </div>
              </div>

              <div className="section-block">
                <h2 className="section-heading"><span className="sec-num">03</span> Ticket Status</h2>
                <table className="compact-table">
                  <thead>
                    <tr>
                      <th>Status</th>
                      <th>Count</th>
                      <th>Share</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td><span className="badge" style={{ background: "#FEF3C7", color: "#B45309" }}>Open</span></td>
                      <td className="num">368</td>
                      <td>
                        <div className="bar-wrap"><div className="bar" style={{ width: "99.7%", background: "#F59E0B" }} /></div>
                        <span className="pct">99.7%</span>
                      </td>
                    </tr>
                    <tr>
                      <td><span className="badge" style={{ background: "#D1FAE5", color: "#065F46" }}>Completed</span></td>
                      <td className="num">1</td>
                      <td>
                        <div className="bar-wrap"><div className="bar" style={{ width: "0.3%", minWidth: 2, background: "#10B981" }} /></div>
                        <span className="pct">0.3%</span>
                      </td>
                    </tr>
                    <tr>
                      <td><span className="badge" style={{ background: "#FEE2E2", color: "#B91C1C" }}>SLA Breached</span></td>
                      <td className="num">368</td>
                      <td>
                        <div className="bar-wrap"><div className="bar" style={{ width: "99.7%", background: "#EF4444" }} /></div>
                        <span className="pct">99.7%</span>
                      </td>
                    </tr>
                  </tbody>
                </table>
                <div className="alert-strip red">{"\u26A0"} SLA breach rate critically high at 99.7% — immediate intervention required.</div>
              </div>
            </div>

            <div className="col-right">
              <div className="section-block">
                <h2 className="section-heading"><span className="sec-num">04</span> Team Performance</h2>

                <p className="sub-label">Regional Supervisors — 905 tickets · 0.0% completion</p>
                <table className="compact-table">
                  <thead>
                    <tr><th>Name</th><th>Region</th><th>Total</th><th>Rate</th></tr>
                  </thead>
                  <tbody>
                    {supervisors.map((s) => (
                      <tr key={s.name}>
                        <td className="name">{s.name}</td>
                        <td className="muted">{s.region}</td>
                        <td className="num">{s.total}</td>
                        <td className="num red-text">0.0%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>

                <p className="sub-label" style={{ marginTop: 16 }}>Field Engineers — 179 tickets · 0.6% completion</p>
                {engineers.map((eng) => (
                  <div key={eng.name} className="eng-row">
                    <div className="eng-top">
                      <span className="eng-name">{eng.name}</span>
                      <span className="eng-rate" style={{ color: eng.rate === "0.0%" ? "#EF4444" : "#10B981" }}>{eng.rate}</span>
                    </div>
                    <div className="eng-bar-track">
                      <div className="eng-bar-fill" style={{ width: `${(eng.completed / eng.total) * 100 || 0.5}%`, background: eng.color, minWidth: 3 }} />
                      <span className="eng-count">{eng.completed}/{eng.total}</span>
                    </div>
                  </div>
                ))}

                <div className="alert-strip amber" style={{ marginTop: 12 }}>{"\u26A0"} Low throughput: Review workload distribution and resource capacity.</div>
              </div>

              <div className="section-block">
                <h2 className="section-heading"><span className="sec-num">05</span> Recommendations</h2>
                <div className="rec-list">
                  {[
                    ["\uD83D\uDD0D", "Conduct end-to-end workflow audit to identify bottlenecks in ticket resolution."],
                    ["\u26A1", "Implement automated SLA escalation protocols for approaching-threshold tickets."],
                    ["\u2696\uFE0F", "Redistribute ticket assignments across active engineers to balance workload."],
                    ["\uD83C\uDFAF", "Perform root-cause analysis starting with 5 supervisors at 0.0% completion."],
                    ["\uD83D\uDC65", "Activate idle engineers — only 11 of 26 are currently contributing."],
                    ["\uD83D\uDCE6", "Initiate inventory tracking; zero transactions recorded signals oversight gap."],
                  ].map(([icon, text]) => (
                    <div key={text as string} className="rec-item">
                      <span className="rec-icon">{icon}</span>
                      <span className="rec-text">{text}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="page-footer">
          <span>Saudi Awwal Bank — Project Performance Report · 11 March 2026 · Confidential</span>
          <span>Powered by Onasi · © 2026 Onasi-CloudTech</span>
        </div>
      </div>

    </div>
  );
}
