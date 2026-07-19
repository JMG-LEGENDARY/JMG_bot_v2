import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useMemo, useRef, useState } from "react";
import { motion } from "framer-motion";
import {
  LineChart, Line, XAxis, YAxis, ResponsiveContainer, Tooltip, CartesianGrid,
} from "recharts";
import {
  Bot, Cpu, Database, Server, Activity, Coins, ShoppingCart, Shield, Gamepad2,
  ChevronRight, Zap, Users, MessageSquare, Radio, Settings2, Wifi, WifiOff,
  ArrowRight, Github, BookOpen, MemoryStick, HardDrive, Clock,
} from "lucide-react";
import {
  Accordion, AccordionContent, AccordionItem, AccordionTrigger,
} from "@/components/ui/accordion";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

export const Route = createFileRoute("/")({ component: Landing });

/* ============================================================
   LIVE MONITORING WEBSOCKET HOOK
============================================================ */
type BotHealth = "stable" | "lagging" | "unresponsive" | "offline";

type LiveData = {
  bot: {
    health: BotHealth;
    loop_latency_ms: number;
    discord_latency_ms: number;
    uptime_seconds: number;
    memory_mb: number;
    cpu_percent: number;
  };
  minecraft_server: {
    state: "online" | "offline" | "crash" | "starting" | string;
    online_players_count: number;
    last_events: string[];
  };
};

type ChartPoint = { t: number; loop: number; discord: number };

const MAX_POINTS = 60;
const DEFAULT_WS = "ws://127.0.0.1:8000/api/v1/live";

function useLiveMonitoring(wsUrl: string) {
  const [data, setData] = useState<LiveData | null>(null);
  const [health, setHealth] = useState<BotHealth>("offline");
  const [chart, setChart] = useState<ChartPoint[]>(
    Array.from({ length: MAX_POINTS }, (_, i) => ({ t: i, loop: 0, discord: 0 })),
  );
  const socketRef = useRef<WebSocket | null>(null);
  const reconnectRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const stoppedRef = useRef(false);

  useEffect(() => {
    stoppedRef.current = false;

    const connect = () => {
      if (stoppedRef.current) return;
      let socket: WebSocket;
      try {
        socket = new WebSocket(wsUrl);
      } catch {
        setHealth("offline");
        reconnectRef.current = setTimeout(connect, 4000);
        return;
      }
      socketRef.current = socket;

      socket.onopen = () => setHealth("stable");
      socket.onmessage = (ev) => {
        try {
          const payload: LiveData = JSON.parse(ev.data);
          setData(payload);
          setHealth(payload.bot.health);
          setChart((prev) => {
            const next = prev.slice(1);
            next.push({
              t: (prev[prev.length - 1]?.t ?? 0) + 1,
              loop: payload.bot.loop_latency_ms,
              discord: payload.bot.discord_latency_ms,
            });
            return next;
          });
        } catch {
          /* ignore malformed frame */
        }
      };
      socket.onclose = () => {
        setHealth("offline");
        if (!stoppedRef.current) reconnectRef.current = setTimeout(connect, 4000);
      };
      socket.onerror = () => {
        try { socket.close(); } catch { /* noop */ }
      };
    };

    connect();

    return () => {
      stoppedRef.current = true;
      if (reconnectRef.current) clearTimeout(reconnectRef.current);
      try { socketRef.current?.close(); } catch { /* noop */ }
    };
  }, [wsUrl]);

  return { data, health, chart };
}

/* ============================================================
   NAV
============================================================ */
function Nav({ status }: { status: BotHealth }) {
  const dotClass =
    status === "stable" ? "bg-accent"
    : status === "lagging" ? "bg-yellow-400"
    : status === "unresponsive" ? "bg-red-500"
    : "bg-muted-foreground";
  const label =
    status === "stable" ? "Live Synced"
    : status === "lagging" ? "Loop Lagging"
    : status === "unresponsive" ? "Unresponsive"
    : "Disconnected";

  return (
    <header className="fixed top-0 inset-x-0 z-50 glass-strong border-b border-white/5">
      <div className="mx-auto max-w-7xl px-4 h-14 flex items-center justify-between">
        <a href="#top" className="flex items-center gap-2 font-display font-bold">
          <Bot className="w-5 h-5 text-neon" />
          <span className="neon-text">JMG Bot v2</span>
        </a>
        <nav className="hidden md:flex items-center gap-6 text-sm text-muted-foreground">
          <a href="#monitoring" className="hover:text-foreground transition-colors">Monitoring</a>
          <a href="#features" className="hover:text-foreground transition-colors">Features</a>
          <a href="#commands" className="hover:text-foreground transition-colors">Commands</a>
          <a href="#architecture" className="hover:text-foreground transition-colors">Architecture</a>
        </nav>
        <div className="flex items-center gap-2 text-xs font-mono">
          <span className={`w-2 h-2 rounded-full ${dotClass} pulse-dot`} />
          <span className="text-muted-foreground">{label}</span>
        </div>
      </div>
    </header>
  );
}

/* ============================================================
   HERO
============================================================ */
function Hero({ data, health }: { data: LiveData | null; health: BotHealth }) {
  return (
    <section id="top" className="relative overflow-hidden pt-28 pb-16 md:pt-36 md:pb-24">
      <div className="absolute inset-0 bg-grid opacity-60" />
      <div className="absolute -top-40 left-1/2 -translate-x-1/2 w-[900px] h-[500px] rounded-full blur-3xl opacity-40 pointer-events-none"
           style={{ background: "radial-gradient(closest-side, oklch(0.72 0.20 240 / 0.55), transparent)" }} />

      <div className="relative mx-auto max-w-7xl px-4 grid lg:grid-cols-2 gap-10 items-center">
        <motion.div initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}>
          <div className="inline-flex items-center gap-2 rounded-full glass px-3 py-1 text-xs font-mono text-neon">
            <span className="w-1.5 h-1.5 rounded-full bg-accent pulse-dot" />
            v2.0 · Discord × Minecraft bridge
          </div>
          <h1 className="mt-6 font-display font-black tracking-tight text-5xl md:text-7xl leading-[0.95]">
            <span className="neon-text">JMG Bot v2</span>
          </h1>
          <p className="mt-6 max-w-xl text-lg text-muted-foreground">
            High-performance Discord bot for Minecraft server management,
            CraftyCoin economy and real-time monitoring — connected to your
            Crafty Controller API via WebSocket.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <a href="#monitoring"
               className="group inline-flex items-center gap-2 rounded-lg px-5 py-3 font-semibold text-primary-foreground glow-blue transition-transform hover:-translate-y-0.5"
               style={{ background: "linear-gradient(135deg, oklch(0.75 0.22 240), oklch(0.60 0.22 260))" }}>
              Open Live Dashboard
              <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-1" />
            </a>
            <a href="#commands"
               className="inline-flex items-center gap-2 rounded-lg px-5 py-3 font-semibold glass-strong hover:bg-white/5 transition-colors">
              Browse Commands
            </a>
          </div>
        </motion.div>

        <LiveHealthCard data={data} health={health} />
      </div>
    </section>
  );
}

function LiveHealthCard({ data, health }: { data: LiveData | null; health: BotHealth }) {
  const loop = data?.bot.loop_latency_ms ?? 0;
  const discord = data?.bot.discord_latency_ms ?? 0;
  const uptime = data?.bot.uptime_seconds ?? 0;
  const hrs = Math.floor(uptime / 3600);
  const mins = Math.floor((uptime % 3600) / 60);
  const connected = health !== "offline";

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.6, delay: 0.1 }}
      className="glass-strong rounded-2xl p-6 relative overflow-hidden"
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm font-mono">
          {connected ? <Wifi className="w-4 h-4 text-accent" /> : <WifiOff className="w-4 h-4 text-red-400" />}
          <span className="text-muted-foreground">Live feed</span>
        </div>
        <Badge variant="outline" className="font-mono text-xs">
          {connected ? "WS · connected" : "WS · offline"}
        </Badge>
      </div>

      <div className="mt-6 grid grid-cols-2 gap-4">
        <Metric label="Event Loop" value={loop} unit="ms" icon={Activity} live={connected} />
        <Metric label="Discord GW" value={discord} unit="ms" icon={Radio} live={connected} />
        <Metric label="Memory" value={data?.bot.memory_mb ?? 0} unit="Mo" icon={MemoryStick} live={connected} />
        <Metric label="CPU" value={data?.bot.cpu_percent ?? 0} unit="%" icon={Cpu} live={connected} />
      </div>

      <div className="mt-6 flex items-center justify-between text-xs font-mono text-muted-foreground border-t border-white/5 pt-4">
        <span className="flex items-center gap-1.5"><Clock className="w-3.5 h-3.5" /> Uptime {hrs}h {mins}m</span>
        <span className="flex items-center gap-1.5">
          <Server className="w-3.5 h-3.5" />
          MC: {data?.minecraft_server.state?.toUpperCase() ?? "—"}
          {" · "}
          {data?.minecraft_server.online_players_count ?? 0} players
        </span>
      </div>
    </motion.div>
  );
}

function Metric({
  label, value, unit, icon: Icon, live,
}: {
  label: string; value: number; unit: string; icon: React.ElementType; live: boolean;
}) {
  return (
    <div className="rounded-xl bg-black/20 border border-white/5 p-4">
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <Icon className="w-3.5 h-3.5" /> {label}
      </div>
      <div className="mt-2 font-display text-2xl font-bold">
        {live ? value : "—"}
        <span className="ml-1 text-sm text-muted-foreground font-mono">{unit}</span>
      </div>
    </div>
  );
}

/* ============================================================
   MONITORING SECTION
============================================================ */
function MonitoringSection({
  wsUrl, setWsUrl, data, health, chart,
}: {
  wsUrl: string; setWsUrl: (v: string) => void;
  data: LiveData | null; health: BotHealth; chart: ChartPoint[];
}) {
  const [draftUrl, setDraftUrl] = useState(wsUrl);
  useEffect(() => setDraftUrl(wsUrl), [wsUrl]);

  const stateColor =
    data?.minecraft_server.state === "online" ? "text-accent"
    : data?.minecraft_server.state === "crash" ? "text-red-400"
    : "text-muted-foreground";

  const strokeColor =
    health === "unresponsive" ? "#ff3366"
    : health === "lagging" ? "#ffaa00"
    : "#00b4d8";

  return (
    <section id="monitoring" className="relative py-20 md:py-28">
      <div className="mx-auto max-w-7xl px-4">
        <div className="flex flex-wrap items-end justify-between gap-4 mb-8">
          <div>
            <div className="text-xs font-mono text-neon uppercase tracking-widest">Live monitoring</div>
            <h2 className="mt-2 font-display font-bold text-3xl md:text-4xl">Real-time bot telemetry</h2>
            <p className="mt-2 text-muted-foreground max-w-2xl">
              Streaming from your bot's WebSocket endpoint. Metrics update every 500&nbsp;ms.
            </p>
          </div>
          <div className="glass rounded-xl p-3 flex items-center gap-2">
            <Settings2 className="w-4 h-4 text-muted-foreground" />
            <Input
              value={draftUrl}
              onChange={(e) => setDraftUrl(e.target.value)}
              placeholder={DEFAULT_WS}
              className="w-72 h-9 bg-black/30 font-mono text-xs"
            />
            <Button size="sm" onClick={() => setWsUrl(draftUrl)}>Connect</Button>
          </div>
        </div>

        <div className="grid lg:grid-cols-3 gap-4">
          <StatCard icon={Activity} label="Event Loop Latency" value={data?.bot.loop_latency_ms ?? 0} unit="ms" tone={strokeColor} live={health !== "offline"} />
          <StatCard icon={Radio} label="Discord Gateway" value={data?.bot.discord_latency_ms ?? 0} unit="ms" live={health !== "offline"} />
          <StatCard icon={Users} label="Players Online" value={data?.minecraft_server.online_players_count ?? 0} unit="" live={health !== "offline"} />
          <StatCard icon={MemoryStick} label="Memory" value={data?.bot.memory_mb ?? 0} unit="Mo" live={health !== "offline"} />
          <StatCard icon={Cpu} label="CPU Load" value={data?.bot.cpu_percent ?? 0} unit="%" live={health !== "offline"} />
          <StatCard icon={HardDrive} label="MC Server" value={0} unit="" custom={
            <div className={`font-display text-2xl font-bold ${stateColor}`}>
              {data?.minecraft_server.state?.toUpperCase() ?? "—"}
            </div>
          } live={health !== "offline"} />
        </div>

        <div className="mt-6 grid lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2 glass-strong rounded-2xl p-5">
            <div className="flex items-center justify-between mb-3">
              <div>
                <div className="text-sm font-semibold">Latency (last 30s)</div>
                <div className="text-xs text-muted-foreground font-mono">Loop vs Discord Gateway · 0.5s tick</div>
              </div>
              <div className="flex gap-4 text-xs font-mono">
                <span className="flex items-center gap-1.5">
                  <span className="w-3 h-0.5" style={{ background: strokeColor }} /> Loop
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="w-3 h-0.5 border-t border-dashed" style={{ borderColor: "rgba(114,137,218,0.7)" }} /> Discord
                </span>
              </div>
            </div>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chart}>
                  <CartesianGrid stroke="rgba(255,255,255,0.04)" vertical={false} />
                  <XAxis dataKey="t" hide />
                  <YAxis stroke="#8a99ad" fontSize={10} tickLine={false} axisLine={false} domain={[0, (dataMax: number) => Math.max(10, dataMax)]} />
                  <Tooltip
                    contentStyle={{ background: "rgba(13,14,18,0.95)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 8, fontSize: 12 }}
                    labelStyle={{ color: "#8a99ad" }}
                  />
                  <Line type="monotone" dataKey="loop" stroke={strokeColor} strokeWidth={2} dot={false} isAnimationActive={false} name="Loop (ms)" />
                  <Line type="monotone" dataKey="discord" stroke="rgba(114,137,218,0.6)" strokeWidth={1.5} strokeDasharray="4 4" dot={false} isAnimationActive={false} name="Discord (ms)" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="glass-strong rounded-2xl p-5 flex flex-col">
            <div className="flex items-center justify-between mb-3">
              <div className="text-sm font-semibold flex items-center gap-2">
                <MessageSquare className="w-4 h-4 text-neon" /> Minecraft events
              </div>
              <Badge variant="outline" className="font-mono text-[10px]">last {data?.minecraft_server.last_events?.length ?? 0}</Badge>
            </div>
            <ul className="flex-1 overflow-auto space-y-1.5 font-mono text-xs">
              {(data?.minecraft_server.last_events?.length ?? 0) === 0 ? (
                <li className="text-muted-foreground">No recent event.</li>
              ) : (
                data!.minecraft_server.last_events.slice().reverse().map((ev, i) => (
                  <li key={i} className="rounded-md bg-black/25 border border-white/5 px-2.5 py-1.5 text-muted-foreground">
                    {ev}
                  </li>
                ))
              )}
            </ul>
          </div>
        </div>
      </div>
    </section>
  );
}

function StatCard({
  icon: Icon, label, value, unit, tone, custom, live,
}: {
  icon: React.ElementType; label: string; value: number; unit: string; tone?: string;
  custom?: React.ReactNode; live: boolean;
}) {
  return (
    <div className="glass rounded-xl p-4">
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <Icon className="w-3.5 h-3.5" /> {label}
      </div>
      {custom ?? (
        <div className="mt-2 font-display text-2xl font-bold" style={tone ? { color: tone } : undefined}>
          {live ? value : "—"}
          {unit && <span className="ml-1 text-sm text-muted-foreground font-mono">{unit}</span>}
        </div>
      )}
    </div>
  );
}

/* ============================================================
   FEATURES (accordion)
============================================================ */
const FEATURES = [
  {
    id: "economy", icon: Coins, title: "CraftyCoin economy",
    summary: "In-chat currency earned by activity, redeemable in the shop.",
    points: [
      "Earn CC on Discord messages (anti-spam filtered)",
      "Vocal presence rewards while connected in a voice channel",
      "Persistent balances stored in the SQLite database",
      "Admin adjustments via /economy set|add|remove",
    ],
  },
  {
    id: "shop", icon: ShoppingCart, title: "Automated Minecraft shop",
    summary: "Buy in Discord, delivery is pushed to the Minecraft server.",
    points: [
      "Purchases queued as pending deliveries",
      "cogs/purchase.py drives automatic in-game delivery via Crafty API",
      "Catalog managed from the admin cog",
      "Discord embed receipts with transaction ID",
    ],
  },
  {
    id: "monitoring", icon: Activity, title: "Real-time monitoring",
    summary: "WebSocket stream of loop, gateway, CPU, RAM and MC state.",
    points: [
      "Health classifier: stable · lagging · unresponsive",
      "500 ms tick, 60-point rolling window",
      "Last Minecraft server events surfaced live",
      "Auto-reconnect on socket drop",
    ],
  },
  {
    id: "games", icon: Gamepad2, title: "Casino mini-games",
    summary: "CC-based games with balanced payouts.",
    points: [
      "Dice, coinflip and slot commands",
      "Per-user cooldowns to avoid abuse",
      "House edge tuned in core/economy.py",
    ],
  },
  {
    id: "security", icon: Shield, title: "Anti-spam & moderation",
    summary: "Message rate limiting and role-scoped commands.",
    points: [
      "Sliding-window rate limits per user",
      "Admin-only commands gated by role checks",
      "Structured logs for audits",
    ],
  },
];

function FeaturesSection() {
  return (
    <section id="features" className="relative py-20 md:py-28">
      <div className="mx-auto max-w-5xl px-4">
        <div className="text-xs font-mono text-neon uppercase tracking-widest">What it does</div>
        <h2 className="mt-2 font-display font-bold text-3xl md:text-4xl">Features</h2>
        <p className="mt-2 text-muted-foreground">Everything shipped in the current v2 build.</p>

        <Accordion type="single" collapsible defaultValue="economy" className="mt-8 glass-strong rounded-2xl px-4">
          {FEATURES.map((f) => (
            <AccordionItem key={f.id} value={f.id} className="border-white/5">
              <AccordionTrigger className="hover:no-underline">
                <div className="flex items-center gap-3 text-left">
                  <div className="w-9 h-9 rounded-lg bg-black/30 border border-white/5 flex items-center justify-center">
                    <f.icon className="w-4 h-4 text-neon" />
                  </div>
                  <div>
                    <div className="font-semibold">{f.title}</div>
                    <div className="text-xs text-muted-foreground font-normal">{f.summary}</div>
                  </div>
                </div>
              </AccordionTrigger>
              <AccordionContent>
                <ul className="pl-12 space-y-2 text-sm text-muted-foreground">
                  {f.points.map((p) => (
                    <li key={p} className="flex items-start gap-2">
                      <ChevronRight className="w-4 h-4 text-accent mt-0.5 shrink-0" />
                      <span>{p}</span>
                    </li>
                  ))}
                </ul>
              </AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      </div>
    </section>
  );
}

/* ============================================================
   COMMANDS (dropdown scope + accordion list)
============================================================ */
type Command = {
  name: string; scope: "player" | "admin"; category: string;
  description: string; usage: string;
};
const COMMANDS: Command[] = [
  { name: "/balance", scope: "player", category: "Economy", description: "Show your CraftyCoin balance.", usage: "/balance" },
  { name: "/pay", scope: "player", category: "Economy", description: "Transfer CC to another user.", usage: "/pay <user> <amount>" },
  { name: "/leaderboard", scope: "player", category: "Economy", description: "Top CC holders on the server.", usage: "/leaderboard" },
  { name: "/shop", scope: "player", category: "Shop", description: "Open the Minecraft shop catalog.", usage: "/shop" },
  { name: "/buy", scope: "player", category: "Shop", description: "Purchase an item; delivery is pushed in-game.", usage: "/buy <item_id>" },
  { name: "/orders", scope: "player", category: "Shop", description: "List your pending and delivered orders.", usage: "/orders" },
  { name: "/dice", scope: "player", category: "Games", description: "Roll dice for CC.", usage: "/dice <bet>" },
  { name: "/coinflip", scope: "player", category: "Games", description: "50/50 coin flip against the house.", usage: "/coinflip <bet> <side>" },
  { name: "/status", scope: "player", category: "Monitoring", description: "Bot + Minecraft server health snapshot.", usage: "/status" },
  { name: "/players", scope: "player", category: "Monitoring", description: "Currently connected players.", usage: "/players" },
  { name: "/economy", scope: "admin", category: "Economy", description: "Adjust a user's balance.", usage: "/economy <set|add|remove> <user> <amount>" },
  { name: "/shop-add", scope: "admin", category: "Shop", description: "Add an item to the shop.", usage: "/shop-add <id> <price> <command>" },
  { name: "/shop-remove", scope: "admin", category: "Shop", description: "Remove an item from the shop.", usage: "/shop-remove <id>" },
  { name: "/mc", scope: "admin", category: "Server", description: "Send a raw command to the Minecraft server.", usage: "/mc <command>" },
  { name: "/restart", scope: "admin", category: "Server", description: "Restart the MC server via Crafty API.", usage: "/restart" },
];

function CommandsSection() {
  const [scope, setScope] = useState<"all" | "player" | "admin">("all");
  const [category, setCategory] = useState<string>("all");

  const categories = useMemo(
    () => Array.from(new Set(COMMANDS.map((c) => c.category))),
    [],
  );
  const filtered = COMMANDS.filter(
    (c) => (scope === "all" || c.scope === scope) && (category === "all" || c.category === category),
  );

  return (
    <section id="commands" className="relative py-20 md:py-28">
      <div className="mx-auto max-w-5xl px-4">
        <div className="text-xs font-mono text-neon uppercase tracking-widest">Command reference</div>
        <h2 className="mt-2 font-display font-bold text-3xl md:text-4xl">Commands</h2>
        <p className="mt-2 text-muted-foreground">
          Filter by scope and category, expand any command for its usage.
        </p>

        <div className="mt-6 flex flex-wrap gap-3">
          <Select value={scope} onValueChange={(v) => setScope(v as typeof scope)}>
            <SelectTrigger className="w-40 glass"><SelectValue placeholder="Scope" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All scopes</SelectItem>
              <SelectItem value="player">Player</SelectItem>
              <SelectItem value="admin">Admin</SelectItem>
            </SelectContent>
          </Select>

          <Select value={category} onValueChange={setCategory}>
            <SelectTrigger className="w-48 glass"><SelectValue placeholder="Category" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All categories</SelectItem>
              {categories.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}
            </SelectContent>
          </Select>

          <div className="ml-auto text-xs font-mono text-muted-foreground self-center">
            {filtered.length} / {COMMANDS.length} commands
          </div>
        </div>

        <Accordion type="multiple" className="mt-6 glass-strong rounded-2xl px-4">
          {filtered.map((cmd) => (
            <AccordionItem key={cmd.name} value={cmd.name} className="border-white/5">
              <AccordionTrigger className="hover:no-underline">
                <div className="flex items-center gap-3 text-left w-full">
                  <code className="font-mono text-sm text-neon">{cmd.name}</code>
                  <Badge variant="outline" className="text-[10px] font-mono">{cmd.category}</Badge>
                  <Badge className={`text-[10px] font-mono ml-auto mr-3 ${cmd.scope === "admin" ? "bg-red-500/15 text-red-300 border border-red-500/30" : "bg-accent/15 text-accent border border-accent/30"}`}>
                    {cmd.scope}
                  </Badge>
                </div>
              </AccordionTrigger>
              <AccordionContent>
                <div className="pl-2 space-y-2 text-sm">
                  <p className="text-muted-foreground">{cmd.description}</p>
                  <div className="rounded-md bg-black/30 border border-white/5 p-3 font-mono text-xs">
                    <span className="text-muted-foreground">usage · </span>
                    <span className="text-foreground">{cmd.usage}</span>
                  </div>
                </div>
              </AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      </div>
    </section>
  );
}

/* ============================================================
   ARCHITECTURE (accordion)
============================================================ */
const ARCH = [
  { path: "main.py", role: "Bot bootstrap", detail: "Loads .env, initializes discord.py client, registers cogs and opens the DB pool." },
  { path: "cogs/economy.py", role: "CraftyCoin economy", detail: "Message and vocal earn hooks, /balance, /pay, /leaderboard." },
  { path: "cogs/shop.py", role: "Shop catalog", detail: "Displays items, validates purchase, writes pending order." },
  { path: "cogs/purchase.py", role: "Delivery worker", detail: "Consumes pending orders and pushes commands to the MC server via Crafty API." },
  { path: "cogs/monitoring.py", role: "Live telemetry", detail: "Broadcasts loop/gateway/CPU/RAM and MC state over /api/v1/live WebSocket." },
  { path: "cogs/games.py", role: "Mini-games", detail: "Dice, coinflip and slots with cooldowns and payout logic." },
  { path: "cogs/admin.py", role: "Admin commands", detail: "Role-gated shop and economy management." },
  { path: "core/crafty.py", role: "Crafty API client", detail: "REST wrapper for server state, players and command execution." },
  { path: "core/economy.py", role: "Economy rules", detail: "Earn rates, anti-spam window and payout math." },
  { path: "db/schema.sql", role: "SQLite schema", detail: "Tables: users, balances, orders, events." },
  { path: "utils/logger.py", role: "Structured logs", detail: "JSON logger shared by cogs and workers." },
];

function ArchitectureSection() {
  return (
    <section id="architecture" className="relative py-20 md:py-28">
      <div className="mx-auto max-w-5xl px-4">
        <div className="text-xs font-mono text-neon uppercase tracking-widest">Codebase</div>
        <h2 className="mt-2 font-display font-bold text-3xl md:text-4xl">Architecture</h2>
        <p className="mt-2 text-muted-foreground">Each module and its responsibility.</p>

        <Accordion type="single" collapsible className="mt-8 glass-strong rounded-2xl px-4">
          {ARCH.map((m) => (
            <AccordionItem key={m.path} value={m.path} className="border-white/5">
              <AccordionTrigger className="hover:no-underline">
                <div className="flex items-center gap-3 text-left w-full">
                  <Database className="w-4 h-4 text-neon shrink-0" />
                  <code className="font-mono text-sm">{m.path}</code>
                  <span className="ml-auto mr-3 text-xs text-muted-foreground">{m.role}</span>
                </div>
              </AccordionTrigger>
              <AccordionContent>
                <p className="pl-7 text-sm text-muted-foreground">{m.detail}</p>
              </AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      </div>
    </section>
  );
}

/* ============================================================
   FOOTER
============================================================ */
function Footer() {
  return (
    <footer className="border-t border-white/5 py-10">
      <div className="mx-auto max-w-7xl px-4 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <Bot className="w-4 h-4 text-neon" />
          <span className="font-display font-bold">JMG Bot v2</span>
          <span className="text-xs text-muted-foreground font-mono ml-2">Discord × Minecraft</span>
        </div>
        <div className="flex items-center gap-4 text-sm text-muted-foreground">
          <a href="#monitoring" className="hover:text-foreground flex items-center gap-1.5"><Zap className="w-4 h-4" /> Live</a>
          <a href="#commands" className="hover:text-foreground flex items-center gap-1.5"><BookOpen className="w-4 h-4" /> Docs</a>
          <a href="#" className="hover:text-foreground flex items-center gap-1.5"><Github className="w-4 h-4" /> Source</a>
        </div>
      </div>
    </footer>
  );
}

/* ============================================================
   PAGE
============================================================ */
function Landing() {
  const [wsUrl, setWsUrl] = useState<string>(() => {
    if (typeof window === "undefined") return DEFAULT_WS;
    return localStorage.getItem("jmg_ws_url") ?? DEFAULT_WS;
  });
  useEffect(() => {
    if (typeof window !== "undefined") localStorage.setItem("jmg_ws_url", wsUrl);
  }, [wsUrl]);
  const { data, health, chart } = useLiveMonitoring(wsUrl);

  return (
    <div className="min-h-screen">
      <Nav status={health} />
      <Hero data={data} health={health} />
      <MonitoringSection wsUrl={wsUrl} setWsUrl={setWsUrl} data={data} health={health} chart={chart} />
      <FeaturesSection />
      <CommandsSection />
      <ArchitectureSection />
      <Footer />
    </div>
  );
}
