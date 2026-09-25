import { lazy, Suspense, useEffect, useRef, useState } from 'react';
import {
  AlertCircle,
  AlertTriangle,
  Beaker,
  BookOpen,
  ChevronDown,
  Database,
  Download,
  FileText,
  GitCommit,
  Info,
  Layers3,
  ListChecks,
  ShieldCheck,
} from 'lucide-react';

const InstrumentHero = lazy(() => import('./InstrumentHero.jsx'));

const panel = 'instrument-panel rounded-[1.35rem] border border-slate-700/70 bg-slate-950/75';
const pill = 'rounded-sm border px-3 py-1.5 text-xs uppercase tracking-[0.12em]';

const warningCategories = [
  {
    key: 'covariance',
    title: 'Ill-conditioned covariance',
    description: 'Candidate-source fits excluded because their covariance was non-finite or exceeded the configured condition-number threshold.',
    test: (warning) => warning.includes('covariance condition number') || warning.includes('covariance matrix contains non-finite'),
    tone: 'quality',
  },
  {
    key: 'convergence',
    title: 'Fit did not converge',
    description: 'Exponential fits excluded after reaching the configured optimizer limit.',
    test: (warning) => warning.includes('failed to converge'),
    tone: 'quality',
  },
  {
    key: 'physical-range',
    title: 'Outside physical range',
    description: 'Numerically returned values rejected by the explicit physical-plausibility gate.',
    test: (warning) => warning.includes('physically plausible range'),
    tone: 'quality',
  },
  {
    key: 'sample-size',
    title: 'Underpowered analysis bin',
    description: 'Reported bin retained transparently, but its sample is below the pre-declared minimum for inference.',
    test: (warning) => warning.includes('below minimum_sample_size'),
    tone: 'caveat',
  },
];

function useJson(path) {
  const [state, setState] = useState({ data: null, error: null, loading: true });
  useEffect(() => {
    let cancelled = false;
    fetch(path)
      .then((response) => {
        if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`);
        return response.json();
      })
      .then((data) => {
        if (!cancelled) setState({ data, error: null, loading: false });
      })
      .catch((error) => {
        if (!cancelled) setState({ data: null, error, loading: false });
      });
    return () => { cancelled = true; };
  }, [path]);
  return state;
}

function useNearViewport() {
  const ref = useRef(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (!ref.current || !('IntersectionObserver' in window)) {
      setVisible(true);
      return undefined;
    }
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { rootMargin: '180px' },
    );
    observer.observe(ref.current);
    return () => observer.disconnect();
  }, []);

  return [ref, visible];
}

function Section({ icon: Icon, eyebrow, title, className = '', children }) {
  return (
    <article className={`${panel} p-5 md:p-6 ${className}`}>
      <div className="mb-5 flex items-start gap-3 border-b border-slate-800 pb-4">
        <span className="section-icon mt-0.5 grid size-8 shrink-0 place-items-center rounded-sm">
          <Icon size={16} aria-hidden="true" />
        </span>
        <div>
          {eyebrow && <p className="instrument-label">{eyebrow}</p>}
          <h2 className="text-lg font-semibold tracking-tight text-slate-100">{title}</h2>
        </div>
      </div>
      {children}
    </article>
  );
}

function MetricCard({ metric, featured = false }) {
  const hasUncertainty = metric.uncertainty_low != null && metric.uncertainty_high != null;
  return (
    <article className={`metric-card relative overflow-hidden border border-slate-700/70 bg-slate-950/80 p-5 ${featured ? 'md:col-span-2' : ''}`}>
      <span className="metric-index" aria-hidden="true" />
      <p className="max-w-[90%] break-words text-xs uppercase tracking-[0.12em] text-slate-400">
        {metric.name.replace(/_/g, ' ')}
      </p>
      <p className={`${featured ? 'text-4xl' : 'text-2xl'} mt-4 font-semibold tabular-nums text-slate-50`}>
        {typeof metric.estimate === 'number' ? metric.estimate.toPrecision(4) : String(metric.estimate)}
        <span className="ml-2 text-xs font-normal uppercase tracking-wide text-blue-300">{metric.units}</span>
      </p>
      {hasUncertainty && (
        <p className="mt-2 font-mono text-xs text-blue-200/75">
          95% CI [{metric.uncertainty_low.toPrecision(3)}, {metric.uncertainty_high.toPrecision(3)}]
        </p>
      )}
      <p className="mt-4 text-xs text-slate-500">sample size <span className="font-mono text-slate-300">n={metric.sample_size}</span></p>
    </article>
  );
}

function RobustnessAudit({ state }) {
  if (state.loading) return <Section icon={Beaker} eyebrow="Sensitivity audit" title="Archive and dependence checks"><p className="text-sm text-slate-400">Loading robustness evidence…</p></Section>;
  if (state.error || !state.data) return <Section icon={AlertCircle} eyebrow="Sensitivity audit" title="Archive and dependence checks"><p className="text-sm text-red-200">Robustness evidence could not be loaded.</p></Section>;
  const audit = state.data;
  const refresh = audit.archive_refresh;
  const exposureValues = Object.values(audit.exposure_medians);
  const deletionValues = Object.values(audit.leave_one_exposure_out_medians);
  return (
    <Section icon={Beaker} eyebrow="Sensitivity audit" title="Archive and dependence checks" className="h-full">
      <div className="evidence-ledger">
        <div><span>Current MAST-byte median</span><strong>{refresh.current_median_suppression.toFixed(3)}</strong></div>
        <div><span>Prior manifest-byte median</span><strong>{refresh.baseline_median_suppression.toFixed(3)}</strong></div>
        <div><span>Coordinate-cluster median</span><strong>{audit.cluster_median_suppression.toFixed(3)}</strong></div>
        <div><span>Cluster bootstrap 95% interval</span><strong>[{audit.cluster_bootstrap_95_interval.map((value) => value.toFixed(3)).join(', ')}]</strong></div>
        <div><span>Single-exposure medians</span><strong>{Math.min(...exposureValues).toFixed(3)}–{Math.max(...exposureValues).toFixed(3)}</strong></div>
        <div><span>Leave-one-exposure-out</span><strong>{Math.min(...deletionValues).toFixed(3)}–{Math.max(...deletionValues).toFixed(3)}</strong></div>
      </div>
      <p className="mt-5 border-l-2 border-amber-500/70 pl-4 text-sm leading-relaxed text-slate-300">
        All six archive hashes changed after reprocessing. The direction remains positive, but the estimator is not numerically stable enough for a population-level calibration claim.
      </p>
      <p className="mt-4 text-xs leading-relaxed text-slate-500">{audit.claim_boundary}</p>
    </Section>
  );
}

function WarningAudit({ state }) {
  if (state.loading) return <p className="text-sm text-slate-400">Loading audit records…</p>;
  if (state.error) {
    return (
      <div className="flex gap-3 rounded-sm border border-red-800/80 bg-red-950/35 p-4 text-sm text-red-200">
        <AlertCircle size={18} className="mt-0.5 shrink-0" aria-hidden="true" />
        Could not load results/warnings.json: {String(state.error)}
      </div>
    );
  }

  const entries = Array.isArray(state.data) ? state.data : [];
  if (entries.length === 0) {
    return (
      <div className="flex gap-3 rounded-sm border border-blue-800/70 bg-blue-950/25 p-4 text-sm text-blue-100">
        <ShieldCheck size={18} className="mt-0.5 shrink-0" aria-hidden="true" />
        No warnings recorded in results/warnings.json.
      </div>
    );
  }

  const claimed = new Set();
  const groups = warningCategories.map((category) => {
    const items = entries.filter((warning, index) => {
      if (claimed.has(index) || !category.test(warning)) return false;
      claimed.add(index);
      return true;
    });
    return { ...category, items };
  }).filter((group) => group.items.length > 0);
  const unclassified = entries.filter((_, index) => !claimed.has(index));
  if (unclassified.length > 0) {
    groups.push({
      key: 'unclassified',
      title: 'Unclassified warning',
      description: 'Audit records without a recognised category; inspect the raw entries below.',
      tone: 'failure',
      items: unclassified,
    });
  }
  const caveatCount = groups.filter((group) => group.tone === 'caveat').reduce((total, group) => total + group.items.length, 0);
  const exclusionCount = entries.length - caveatCount - unclassified.length;

  return (
    <div>
      <div className="mb-5 flex items-start gap-3 rounded-sm border border-blue-800/60 bg-blue-950/25 p-4">
        <Info size={18} className="mt-0.5 shrink-0 text-blue-300" aria-hidden="true" />
        <p className="text-sm leading-relaxed text-slate-300">
          <strong className="text-slate-100">{entries.length} transparent audit records:</strong>{' '}
          {exclusionCount} candidate-fit exclusions and {caveatCount} documented sample-size caveats.
          These are quality-control decisions, not a pipeline crash.
        </p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        {groups.map((group) => (
          <div key={group.key} className={`warning-group warning-${group.tone} rounded-sm border p-4`}>
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-sm font-semibold text-slate-100">{group.title}</p>
                <p className="mt-2 text-xs leading-relaxed text-slate-400">{group.description}</p>
              </div>
              <span className="warning-count shrink-0 font-mono text-lg">{group.items.length}</span>
            </div>
          </div>
        ))}
      </div>
      <details className="raw-warning-list mt-4 rounded-sm border border-slate-700/70 bg-slate-950/70">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-3 p-4 text-sm font-medium text-blue-200">
          <span>Show all {entries.length} raw entries</span>
          <ChevronDown size={17} className="details-chevron shrink-0" aria-hidden="true" />
        </summary>
        <ol className="max-h-[28rem] space-y-2 overflow-y-auto border-t border-slate-800 p-4 pl-10 text-xs leading-relaxed text-slate-400">
          {entries.map((warning, index) => <li key={`${index}-${warning}`} className="pl-1 marker:text-slate-600">{warning}</li>)}
        </ol>
      </details>
    </div>
  );
}

function LazyHero() {
  const [ref, visible] = useNearViewport();
  return (
    <div ref={ref} className="instrument-hero-shell h-[21rem] overflow-hidden rounded-sm border border-blue-800/50 bg-slate-950/90 md:h-[25rem]">
      {visible ? (
        <Suspense fallback={<div className="loading-scan grid h-full place-items-center text-xs uppercase tracking-[0.2em] text-blue-300">Loading instrument model…</div>}>
          <InstrumentHero />
        </Suspense>
      ) : (
        <div className="loading-scan h-full" aria-label="Instrument illustration placeholder" />
      )}
    </div>
  );
}

export default function App() {
  const project = useJson('./project.json');
  const summary = useJson('./results/summary.json');
  const warnings = useJson('./results/warnings.json');
  const benchmarks = useJson('./results/benchmarks.json');
  const robustness = useJson('./results/robustness.json');

  if (project.loading) {
    return <main className="detector-bg grid min-h-screen place-items-center text-sm uppercase tracking-[0.2em] text-blue-200">Loading detector audit…</main>;
  }
  if (project.error || !project.data) {
    return <main className="detector-bg grid min-h-screen place-items-center text-red-300">Could not load project.json: {String(project.error)}</main>;
  }

  const p = project.data;
  const metrics = summary.data?.metrics ?? [];
  const isDemo = summary.data?.data_kind === 'synthetic_smoke_test' || summary.data?.data_kind === 'synthetic_demo';

  return (
    <>
    <a className="skip-link" href="#main">Skip to research evidence</a>
    <main id="main" className="detector-bg min-h-screen">
      <div className="mx-auto max-w-[90rem] px-4 py-6 sm:px-6 lg:px-8 lg:py-10">
        <header className="hero-grid overflow-hidden rounded-[1.6rem] border border-slate-700/70 bg-slate-950/80">
          <div className="flex flex-col justify-between p-6 md:p-9 lg:p-11">
            <div>
              <div className="mb-8 flex items-center gap-3">
                <span className="grid size-9 place-items-center rounded-sm border border-blue-700/70 bg-blue-950/60 text-blue-300"><Layers3 size={18} aria-hidden="true" /></span>
                <div>
                  <p className="instrument-label">Instrument audit · ACS/WFC</p>
                  <p className="text-xs text-slate-500">two-axis charge-transfer diagnostics</p>
                </div>
              </div>
              <p className="mb-4 text-sm font-medium text-blue-300">{p.category}</p>
              <h1 className="max-w-3xl text-4xl font-semibold leading-[1.05] tracking-[-0.04em] text-slate-50 sm:text-5xl lg:text-6xl">{p.title}</h1>
              <p className="mt-6 max-w-3xl text-base leading-relaxed text-slate-300 md:text-lg">{p.question}</p>
            </div>
            <div className="mt-9 flex flex-wrap gap-2">
              <span className={`${pill} border-blue-700/70 bg-blue-950/45 text-blue-200`}>{p.status}</span>
              <span className={`${pill} border-slate-700 text-slate-300`}>Priority {p.priority}/10</span>
              <span className={`${pill} border-slate-700 text-slate-300`}>{p.dataMode}</span>
              {summary.data && (
                <span className={`${pill} ${isDemo ? 'border-amber-700/70 bg-amber-950/30 text-amber-200' : 'border-emerald-700/70 bg-emerald-950/30 text-emerald-200'}`}>
                  {isDemo ? 'Synthetic demo results' : 'Real data results'}
                </span>
              )}
            </div>
          </div>
          <div className="border-t border-slate-800 p-3 lg:border-l lg:border-t-0">
            <LazyHero />
          </div>
        </header>

        {isDemo && (
          <div className="mt-5 flex items-start gap-3 rounded-sm border border-amber-800/70 bg-amber-950/25 p-4 text-sm leading-relaxed text-amber-100">
            <AlertTriangle size={18} className="mt-0.5 shrink-0" aria-hidden="true" />
            The metrics and figures below were generated from clearly labelled synthetic demo data,
            not HST observations. Real-data results replace them automatically after the archive pipeline runs.
          </div>
        )}

        <div className="mt-7 grid gap-7 xl:grid-cols-[0.72fr_1.28fr]">
          <aside className="space-y-7">
            <Section icon={ShieldCheck} eyebrow="Scope control" title="Provenance boundary">
              <p className="text-sm leading-relaxed text-slate-300">{p.novelty}</p>
              <div className="mt-5 border-l-2 border-amber-500/70 bg-amber-950/20 p-4 text-sm leading-relaxed text-amber-100">
                No result is public-ready until validation and provenance checks pass.
              </div>
              {summary.data?.provenance && (
                <dl className="mt-5 space-y-3 text-xs">
                  <div className="flex items-center gap-2"><GitCommit size={14} className="text-blue-400" /><dt className="text-slate-500">git commit</dt><dd className="ml-auto font-mono text-slate-300">{summary.data.provenance.git_commit}</dd></div>
                  <div className="flex items-center gap-2"><FileText size={14} className="text-blue-400" /><dt className="text-slate-500">config sha256</dt><dd className="ml-auto max-w-[10rem] truncate font-mono text-slate-300">{summary.data.provenance.config_sha256 ?? 'n/a'}</dd></div>
                  <div className="flex items-center gap-2"><Beaker size={14} className="text-blue-400" /><dt className="text-slate-500">package version</dt><dd className="ml-auto font-mono text-slate-300">{summary.data.provenance.package_version}</dd></div>
                </dl>
              )}
            </Section>
            <RobustnessAudit state={robustness} />
          </aside>

          <section aria-labelledby="measurement-summary">
            <div className="mb-4 flex items-end justify-between gap-4">
              <div>
                <p className="instrument-label">Readout 01</p>
                <h2 id="measurement-summary" className="text-2xl font-semibold tracking-tight text-slate-100">Measurement summary</h2>
              </div>
              <p className="hidden font-mono text-xs text-slate-500 sm:block">{metrics.length.toString().padStart(2, '0')} channels</p>
            </div>
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {metrics.map((metric, index) => <MetricCard key={metric.name} metric={metric} featured={index === 0} />)}
              {!summary.data && (
                <article className="metric-card border border-slate-700 bg-slate-950/80 p-5">
                  <p className="text-xs uppercase tracking-widest text-slate-400">Result status</p>
                  <p className="mt-4 text-2xl font-semibold">No results yet</p>
                  <p className="mt-2 text-xs text-slate-500">Run scripts/run_analysis.py first.</p>
                </article>
              )}
            </div>
          </section>
        </div>

        <section className="mt-7">
          <Section icon={BookOpen} eyebrow="Readout 02" title="Figure gallery">
            <div className="figure-grid grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {p.figures.map((figure, index) => (
                <figure key={figure.id} className={`figure-card overflow-hidden rounded-sm border border-slate-700/70 bg-slate-900/70 ${index === 0 ? 'md:col-span-2 xl:row-span-2' : ''}`}>
                  <div className="figure-image-wrap bg-[#f7f9fc] p-2">
                    <img
                      src={`./figures/${figure.id}.svg`}
                      alt={figure.label}
                      className="h-full w-full object-contain"
                      loading={index > 1 ? 'lazy' : 'eager'}
                      onError={(event) => { event.currentTarget.style.display = 'none'; }}
                    />
                  </div>
                  <figcaption className="flex items-center justify-between gap-3 px-4 py-3 text-sm text-slate-300">
                    <span>{figure.label}</span>
                    <span className="font-mono text-[0.65rem] text-blue-400">F{String(index + 1).padStart(2, '0')}</span>
                  </figcaption>
                </figure>
              ))}
            </div>
          </Section>
        </section>

        <section className="mt-7 grid gap-7 lg:grid-cols-[0.78fr_1.22fr]">
          <Section icon={ListChecks} eyebrow="Acceptance gates" title="Validation contract">
            <ol className="space-y-3 text-sm text-slate-300">
              {p.validationContract.map((item, index) => (
                <li key={item} className="flex gap-3 border-b border-slate-800 pb-3 last:border-0 last:pb-0">
                  <span className="font-mono text-blue-400">{String(index + 1).padStart(2, '0')}</span>
                  <span>{item}</span>
                </li>
              ))}
            </ol>
          </Section>
          <Section icon={AlertTriangle} eyebrow="Live quality log" title="Warnings and documented caveats">
            <WarningAudit state={warnings} />
          </Section>
        </section>

        <section className="mt-7 grid gap-7 lg:grid-cols-2">
          <Section icon={Beaker} eyebrow="Analysis chain" title="Methodology">
            <p className="text-sm leading-7 text-slate-300">{p.methodology}</p>
          </Section>
          <Section icon={AlertTriangle} eyebrow="Interpretive boundary" title="Assumptions and limitations">
            <p className="instrument-label mb-3">Assumptions</p>
            <ul className="mb-6 space-y-2 text-sm leading-relaxed text-slate-300">
              {p.assumptions.map((assumption) => <li key={assumption} className="border-l border-blue-700/70 pl-3">{assumption}</li>)}
            </ul>
            <p className="instrument-label mb-3">Limitations</p>
            <ul className="space-y-2 text-sm leading-relaxed text-slate-300">
              {p.limitations.map((limitation) => <li key={limitation} className="border-l border-amber-700/70 pl-3">{limitation}</li>)}
            </ul>
          </Section>
        </section>

        <footer className="mt-7 grid gap-7 lg:grid-cols-[1.25fr_0.75fr]">
          <Section icon={Download} eyebrow="Reproducibility" title="Downloads and provenance manifest">
            <div className="flex flex-wrap gap-2 text-sm">
              <a className="download-link" href="./manifest.csv" download>data/manifest.csv</a>
              <a className="download-link" href="./results/summary.json" download>results/summary.json</a>
              <a className="download-link" href="./results/robustness.json" download>results/robustness.json</a>
              <a className="download-link" href="./results/robustness_designs.csv" download>robustness designs</a>
              <a className="download-link" href="./results/measurements.csv" download>measurement ledger</a>
              {benchmarks.data && <a className="download-link" href="./results/benchmarks.json" download>results/benchmarks.json</a>}
            </div>
            <p className="mt-5 text-xs leading-relaxed text-slate-500">
              data/manifest.csv records product_id, source, source_url, retrieved_utc, sha256,
              file_size_bytes, selection_reason and licence_or_terms for every archive product used.
            </p>
          </Section>
          <Section icon={Database} eyebrow="Credit" title="Citation and licence">
            <p className="text-sm text-slate-300">Author: {p.citation.author}</p>
            <p className="mt-2 text-sm text-slate-300">Licence: {p.citation.license}</p>
            <a className="mt-4 inline-block text-sm text-blue-300 underline-offset-4 hover:underline" href={p.citation.repository}>{p.citation.repository}</a>
          </Section>
        </footer>
      </div>
    </main>
    </>
  );
}
