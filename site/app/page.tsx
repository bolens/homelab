const stats = [
  { value: '217', label: 'documented stacks' },
  { value: '214', label: 'Compose projects validated' },
  { value: '3', label: 'ingress trust zones' },
];

export default function Home() {
  return (
    <main>
      <a className="skip-link" href="#topology">Skip to topology</a>
      <header className="site-header">
        <a className="brand" href="#home" aria-label="Homelab Atlas home">
          <span className="brand-mark" aria-hidden="true" /> Homelab Atlas
        </a>
        <nav aria-label="Primary navigation">
          <a href="#topology">Topology</a>
          <a href="#stack-model">Stack model</a>
          <a href="https://gitea.bolens.dev/bolens/homelab">Repository</a>
        </nav>
      </header>

      <section className="hero" id="home" aria-labelledby="hero-title">
        <span className="eyebrow">Portable Docker infrastructure</span>
        <h1 id="hero-title">See the homelab before you deploy it.</h1>
        <p>Explore the ingress paths, shared services, observability layer, and isolated application stacks that make up this self-hosted system.</p>
        <div className="hero-actions">
          <a className="button primary" href="#topology">Explore the live topology</a>
          <a className="button secondary" href="https://gitea.bolens.dev/bolens/homelab">Browse stack examples</a>
        </div>
        <dl className="stats" aria-label="Repository summary">
          {stats.map((stat) => <div key={stat.label}><dt>{stat.label}</dt><dd>{stat.value}</dd></div>)}
        </dl>
      </section>

      <section className="topology-section" id="topology" aria-labelledby="topology-title">
        <div className="section-heading">
          <div><span className="eyebrow">Interactive architecture</span><h2 id="topology-title">Trace how traffic moves</h2></div>
          <a className="text-link" href="/topology.html">Open full screen <span aria-hidden="true">↗</span></a>
        </div>
        <p className="section-intro" id="topology-description">Follow public ingress, private access, service dependencies, VPN egress, telemetry, and operational control paths. The diagram supports keyboard navigation, search, zoom, relationship tracing, and export.</p>
        <div className="topology-frame">
          <iframe src="/topology.html" title="Interactive Docker homelab architecture" aria-describedby="topology-description" loading="eager" />
        </div>
      </section>

      <section className="stack-model" id="stack-model" aria-labelledby="stack-model-title">
        <span className="eyebrow">Operating model</span>
        <h2 id="stack-model-title">Independent stacks, explicit contracts</h2>
        <p>Every service remains a portable Compose example with its own setup, storage, networking, security choices, and verification steps.</p>
      </section>
    </main>
  );
}
