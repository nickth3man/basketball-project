import { LayoutShell } from "../components/LayoutShell";
import { fetchSeasons, runLeaderboards } from "../lib/apiClient";
import {
  PaginatedResponse,
  Season,
  LeaderboardsResponseRow,
} from "../lib/types";

/**
 * Landing page: lightweight snapshot links into core sections and tools.
 * Uses server components only.
 */
export default async function HomePage() {
  // Best-effort snapshot calls; swallow errors to keep landing robust.
  let seasons: PaginatedResponse<Season> | null = null;
  let leaders: PaginatedResponse<LeaderboardsResponseRow> | null = null;

  try {
    seasons = await fetchSeasons({ page: 1, page_size: 5 });
  } catch {
    seasons = null;
  }

  try {
    leaders = await runLeaderboards({
      scope: "player_season",
      stat: "pts_per_g",
      page: 1,
      page_size: 5,
    });
  } catch {
    leaders = null;
  }

  return (
    <LayoutShell>
      <section className="home-grid">
        <div className="home-card">
          <h2>Browse</h2>
          <ul>
            <li>
              <a href="/players">Players index</a>
            </li>
            <li>
              <a href="/teams">Teams index</a>
            </li>
            <li>
              <a href="/seasons">Seasons index</a>
            </li>
            <li>
              <a href="/games">Games index</a>
            </li>
          </ul>
        </div>

        <div className="home-card">
          <h2>Tools</h2>
          <ul>
            <li>
              <a href="/tools/player-season-finder">Player Season Finder</a>
            </li>
            <li>
              <a href="/tools/player-game-finder">Player Game Finder</a>
            </li>
            <li>
              <a href="/tools/team-season-finder">Team Season Finder</a>
            </li>
            <li>
              <a href="/tools/leaderboards">Leaderboards</a>
            </li>
            <li>
              <a href="/tools/splits">Splits</a>
            </li>
          </ul>
        </div>

        <div className="home-card">
          <h2>Recent Seasons</h2>
          {!seasons || seasons.data.length === 0 ? (
            <p className="muted">No season snapshot available.</p>
          ) : (
            <ul>
              {seasons.data.map((s) => (
                <li key={s.season_id}>
                  <a href={`/seasons/${s.season_end_year}`}>
                    {s.season_end_year} {s.lg ?? ""}
                    {s.is_lockout ? " (Lockout)" : ""}
                  </a>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="home-card">
          <h2>Scoring Leaders (sample)</h2>
          {!leaders || leaders.data.length === 0 ? (
            <p className="muted">Leaderboards preview unavailable.</p>
          ) : (
            <ol>
              {leaders.data.map((row, idx) => (
                <li key={`${row.subject_id}-${idx}`}>
                  {row.label}: {row.stat.toFixed(1)}
                </li>
              ))}
            </ol>
          )}
        </div>
      </section>
    </LayoutShell>
  );
}