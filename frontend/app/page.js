"use client";
import { useState } from "react";
 
const Box = "textarea";
const Field = "input";
const FIELDS = ["target_user", "problem", "solution", "price", "riskiest_belief", "market"];
const CRITICS = ["Skeptical user", "Competitor", "Engineer", "Finance"];
const COLORS = { pay: "green", maybe: "gold", no: "red" };
const BADGE = { BUILD: "green", PIVOT: "goldenrod", KILL: "crimson" };
 
// fake data for now; later this comes from Ayesha's backend
const fakeCanvas = { target_user: "gym-goers", problem: "no time to cook", solution: "weekly meal kits",
  price: "", riskiest_belief: "they will pay every week", market: "Lahore" };
const fakeVotes = Array.from({ length: 40 }, (_, i) => ["pay", "maybe", "no"][i % 3]);
const fakeVerdict = {
  score_median: 44, score_min: 38, score_max: 51, recommendation: "PIVOT", evidence_coverage: 0.62,
  flaws: [
    { description: "Gym-goers already use cheap tiffin services", experiment: "Ask 20 gym members what they pay for food now", experiment_cost: "1 day, free", pass_kill_metric: "Kill if fewer than 5 would switch" },
    { description: "Weekly delivery cost is too high in Lahore", experiment: "Get 3 courier quotes", experiment_cost: "2 hours, free", pass_kill_metric: "Kill if delivery is over 25% of price" },
    { description: "Price is unknown", experiment: "Show a fake order page at 2 prices", experiment_cost: "1 day, $10 ads", pass_kill_metric: "Pass if 3% click buy" },
  ],
};
const fakeStats = [
  { tier: "fast", tokens_in: 52000, tokens_out: 9000, latency_ms: 1200, calls: 46 },
  { tier: "ultra", tokens_in: 18000, tokens_out: 2400, latency_ms: 6100, calls: 3 },
];
 
export default function Home() {
  const [idea, setIdea] = useState("");
  const [canvas, setCanvas] = useState(null);
  const [votes, setVotes] = useState([]);
  const [verdict, setVerdict] = useState(null);
 
  function run() {
    setVotes(fakeVotes);
    setVerdict(fakeVerdict);
  }
 
  return (
    <main style={{ maxWidth: 900, margin: "40px auto", fontFamily: "sans-serif" }}>
      <h1>Peperio</h1>
 
      {/* 1. Idea box */}
      <Box rows={4} style={{ width: "100%" }} placeholder="Type your idea..."
        value={idea} onChange={(e) => setIdea(e.target.value)} />
      <button onClick={() => setCanvas(fakeCanvas)}>Check my idea</button>
 
      {/* 2. Idea Canvas */}
      {canvas && (
        <section>
          <h2>Idea Canvas</h2>
          {FIELDS.map((f) => (
            <label key={f} style={{ display: "block", margin: "6px 0" }}>
              {f} {!canvas[f] && <b style={{ color: "orange" }}>missing</b>}
              <Field style={{ width: "100%" }} value={canvas[f]}
                onChange={(e) => setCanvas({ ...canvas, [f]: e.target.value })} />
            </label>
          ))}
          <button onClick={run}>Run</button>
        </section>
      )}
 
      {/* 3. Critic cards */}
      <h2>Critics</h2>
      <div style={{ display: "flex", gap: 12 }}>
        {CRITICS.map((c) => (
          <div key={c} style={{ flex: 1, border: "1px solid #ccc", borderRadius: 8, padding: 12, minHeight: 100 }}>
            <b>{c}</b>
            <p>Waiting...</p>
          </div>
        ))}
      </div>
 
      {/* 4. Customer dots */}
      <h2>40 customers</h2>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(8, 24px)", gap: 8 }}>
        {Array.from({ length: 40 }, (_, i) => (
          <div key={i} style={{ width: 24, height: 24, borderRadius: "50%", background: COLORS[votes[i]] || "#ddd" }} />
        ))}
      </div>
      <p><small>Simulated customers, not market research.</small></p>
 
      {verdict && (
        <section>
          {/* 5. Verdict badge */}
          <h2>Verdict</h2>
          <div style={{ display: "inline-block", padding: "8px 20px", borderRadius: 8, color: "white",
            fontSize: 28, fontWeight: "bold", background: BADGE[verdict.recommendation] }}>
            {verdict.recommendation}
          </div>
 
          {/* 6. Score-range chart: line = lowest to highest score, dot = middle score */}
          <h3>Survival score: {verdict.score_median} (range {verdict.score_min} to {verdict.score_max})</h3>
          <div style={{ position: "relative", height: 24, background: "#333", borderRadius: 12 }}>
            <div style={{ position: "absolute", top: 8, height: 8, background: "#4aa3ff", borderRadius: 4,
              left: verdict.score_min + "%", width: (verdict.score_max - verdict.score_min) + "%" }} />
            <div style={{ position: "absolute", top: 2, width: 20, height: 20, borderRadius: "50%",
              background: "white", left: "calc(" + verdict.score_median + "% - 10px)" }} />
          </div>
          <div style={{ display: "flex", justifyContent: "space-between" }}><small>0</small><small>50</small><small>100</small></div>
          <p>Evidence coverage: {Math.round(verdict.evidence_coverage * 100)}% of critic points have a real source</p>
 
          {/* 7. Top 3 fatal flaws */}
          <h2>Top 3 fatal flaws</h2>
          {verdict.flaws.map((f, i) => (
            <div key={i} style={{ border: "1px solid #ccc", borderRadius: 8, padding: 12, margin: "8px 0" }}>
              <b>{i + 1}. {f.description}</b>
              <p>Cheapest test: {f.experiment} ({f.experiment_cost})</p>
              <p><small>{f.pass_kill_metric}</small></p>
            </div>
          ))}
 
          {/* 8. HUD: tokens and speed per model tier */}
          <h2>HUD</h2>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 4 }}>
            <b>Tier</b><b>Calls</b><b>Tokens in</b><b>Tokens out</b><b>Avg speed</b>
            {fakeStats.map((s) => [
              <span key={s.tier + "t"}>{s.tier}</span>,
              <span key={s.tier + "c"}>{s.calls}</span>,
              <span key={s.tier + "i"}>{s.tokens_in}</span>,
              <span key={s.tier + "o"}>{s.tokens_out}</span>,
              <span key={s.tier + "l"}>{(s.latency_ms / 1000).toFixed(1)} s</span>,
            ])}
          </div>
        </section>
      )}
    </main>
  );
}
 