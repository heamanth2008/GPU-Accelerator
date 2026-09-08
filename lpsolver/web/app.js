const fileInput = document.querySelector('#model-file');
const fileLabel = document.querySelector('#file-label');
const solveButton = document.querySelector('#solve-button');
const status = document.querySelector('#status');
let fileText = '';

document.querySelector('#sample-button').addEventListener('click', async () => {
  try {
    const response = await fetch('/api/sample');
    const sample = await response.json();
    if (!response.ok) throw new Error(sample.error || 'Could not load the bundled sample.');
    fileText = sample.mpsText;
    fileLabel.textContent = sample.filename;
    status.textContent = 'Sample loaded. Click Solve model.';
  } catch (error) { status.textContent = `Error: ${error.message}`; }
});

fileInput.addEventListener('change', async () => {
  const file = fileInput.files[0];
  if (!file) return;
  if (file.size > 10 * 1024 * 1024) { status.textContent = 'The file is larger than 10 MB.'; return; }
  fileText = await file.text();
  fileLabel.textContent = file.name;
  status.textContent = 'Model ready. Choose a backend and solve.';
});

solveButton.addEventListener('click', async () => {
  if (!fileText) { status.textContent = 'Choose an .mps file first.'; return; }
  const backend = document.querySelector('input[name="backend"]:checked').value;
  solveButton.disabled = true;
  solveButton.textContent = 'Solving…';
  status.textContent = backend === 'gpu' ? 'GPU solver is running. Large models can take time.' : 'CPU solver is running.';
  try {
    const response = await fetch('/api/solve', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({mpsText:fileText, backend, maxIterations:Number(document.querySelector('#iterations').value)})});
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || 'The solver could not process this model.');
    render(payload);
    status.textContent = 'Solve completed.';
  } catch (error) { status.textContent = `Error: ${error.message}`; }
  finally { solveButton.disabled = false; solveButton.textContent = 'Solve model'; }
});

function format(value) { return Number.isFinite(value) ? Number(value).toPrecision(8) : '—'; }
function render(data) {
  document.querySelector('#empty-state').hidden = true;
  document.querySelector('#results').hidden = false;
  document.querySelector('#model-name').textContent = data.model.name;
  const resultStatus = document.querySelector('#result-status');
  resultStatus.textContent = data.result.status;
  resultStatus.classList.toggle('warning', data.result.status !== 'optimal' && data.result.status !== 'approximate');
  document.querySelector('#objective').textContent = format(data.result.objective);
  document.querySelector('#elapsed').textContent = `${(data.result.elapsed_sec * 1000).toFixed(2)} ms`;
  document.querySelector('#model-size').textContent = `${data.model.rows} × ${data.model.columns}`;
  const gpu = document.querySelector('#gpu-details');
  if (data.result.device) { gpu.hidden = false; gpu.textContent = `GPU: ${data.result.device}. Iterations: ${data.result.iterations}. Maximum constraint violation: ${format(data.result.max_constraint_violation)}.`; }
  else gpu.hidden = true;
  document.querySelector('#variables').innerHTML = data.variables.map(v => `<tr><td>${escapeHtml(v.name)}</td><td>${format(v.value)}</td></tr>`).join('') || '<tr><td colspan="2">No solution values returned.</td></tr>';
}
function escapeHtml(value) { const box = document.createElement('span'); box.textContent = value; return box.innerHTML; }
