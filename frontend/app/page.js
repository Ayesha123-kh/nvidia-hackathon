"use client";
import { useState } from "react";

const Box = "textarea";
const Field = "input";
const FIELDS = ["target_user", "problem", "solution", "price", "riskiest_belief", "market"];
const CRITICS = ["Skeptical user", "Competitor", "Engineer", "Finance"];
const COLORS = { pay: "green", maybe: "gold", no: "red" };

// fake data for now; later this comes from Ayesha's backend
const fakeCanvas = { target_user: "gym-goers", problem: "no time to cook", solution: "weekly meal kits",
  price: "", riskiest_belief: "they will pay every week", market: "Lahore" };
const fakeVotes = Array.from({ length: 40 }, (_, i) => ["pay", "maybe", "no"][i % 3]);

export default function Home() {
  const [idea, setIdea] = useState("");
  const [canvas, setCanvas] = useState(null);
  const [votes, setVotes] = useState([]);

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
          <button onClick={() => setVotes(fakeVotes)}>Run</button>
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
    </main>
  );
}