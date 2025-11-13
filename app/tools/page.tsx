import { LayoutShell } from "../../components/LayoutShell";

/**
 * Tools hub page.
 *
 * Server component:
 * - Static list of all /tools/* utilities with descriptions and links.
 */
export default function ToolsHomePage() {
  const tools = [
    {
      href: "/tools/player-season-finder",
      name: "Player Season Finder",
      description:
        "Search player seasons across years, teams, and playoffs flags.",
    },
    {
      href: "/tools/player-game-finder",
      name: "Player Game Finder",
      description:
        "Find individual player game lines over configurable season ranges.",
    },
    {
      href: "/tools/team-season-finder",
      name: "Team Season Finder",
      description:
        "Filter team seasons by year range and playoffs/regular season.",
    },
    {
      href: "/tools/team-game-finder",
      name: "Team Game Finder",
      description:
        "Locate team game results with score, opponent, and outcome context.",
    },
    {
      href: "/tools/leaderboards",
      name: "Leaderboards",
      description:
        "Rank players or teams by chosen metrics over selected seasons.",
    },
    {
      href: "/tools/splits",
      name: "Splits",
      description:
        "View performance splits (e.g., home/away or versus opponent) for a player or team.",
    },
    {
      href: "/tools/streak-finder",
      name: "Streak Finder",
      description:
        "Identify notable streaks (e.g., scoring or other metrics) for players or teams.",
    },
    {
      href: "/tools/span-finder",
      name: "Span Finder",
      description:
        "Scan rolling spans of games to find peak stretches by metric.",
    },
    {
      href: "/tools/versus-finder",
      name: "Versus Finder",
      description:
        "Summarize performance for a subject against specific opponents.",
    },
    {
      href: "/tools/event-finder",
      name: "Event Finder",
      description:
        "Search play-by-play events by game, player, team, and event type.",
    },
  ];

  return (
    <LayoutShell title="Tools Hub">
      <section>
        <p className="muted">
          Interactive tools for exploring the local basketball statistics
          dataset. Configure filters, run queries against the FastAPI backend,
          and inspect results in simple sortable tables.
        </p>
      </section>

      <section className="tools-grid">
        {tools.map((tool) => (
          <a key={tool.href} href={tool.href} className="tool-card">
            <h2>{tool.name}</h2>
            <p>{tool.description}</p>
          </a>
        ))}
      </section>
    </LayoutShell>
  );
}