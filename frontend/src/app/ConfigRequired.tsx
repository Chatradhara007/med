import { missingConfig } from '../config';

/**
 * Shown instead of the app when required configuration is absent.
 *
 * A fresh clone has no `frontend/.env` -- it is gitignored -- so this is the
 * first thing a new checkout hits. Without it the app renders a sign-in button
 * that throws into the console and never navigates, which reads as a server
 * fault rather than a missing file.
 */
export const ConfigRequired = () => (
  <div style={{ minHeight: '100vh', background: '#f8fafc', color: '#1e293b', padding: '40px 20px', fontFamily: 'system-ui, sans-serif' }}>
    <div style={{ maxWidth: 680, margin: '0 auto' }}>
      <h1 style={{ marginBottom: 8 }}>CareThread is not configured</h1>
      <p style={{ color: '#64748b', marginTop: 0 }}>
        The web app needs to know which deployed stack to talk to. These
        variables are read at build time, so the dev server must be restarted
        after you set them.
      </p>

      <p style={{ marginBottom: 8 }}><strong>Missing from <code>frontend/.env</code>:</strong></p>
      <ul style={{ lineHeight: 1.8 }}>
        {missingConfig.map((f) => (
          <li key={f.key}>
            <code>{f.key}</code>
            <span style={{ color: '#64748b' }}> — stack output: {f.output}</span>
          </li>
        ))}
      </ul>

      <p style={{ marginBottom: 8 }}><strong>To fix:</strong></p>
      <pre style={{ background: '#0f172a', color: '#e2e8f0', padding: 16, borderRadius: 8, overflowX: 'auto', fontSize: 13 }}>
{`cp frontend/.env.example frontend/.env

# fill in the blanks from the stack outputs:
aws cloudformation describe-stacks --stack-name carethread \\
  --query "Stacks[0].Outputs" --output table

npm run dev   # restart -- Vite only reads .env at startup`}
      </pre>

      <p style={{ color: '#64748b', fontSize: 14 }}>
        None of these values is a secret. They are public identifiers of your
        own stack; no AWS access key belongs in the browser.
      </p>
    </div>
  </div>
);
