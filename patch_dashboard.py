f = open(r'C:\Users\donar\OneDrive\Desktop\Git Hub Projects\log-intelligence-platform\dashboard.html', encoding='utf-8').read()

# Find and replace using index
start = f.find('function updateMetrics() {')
end = f.find('\n}', start) + 2  # include the closing }

old = f[start:end]
print("Found block, length:", len(old))

new = """async function updateMetrics() {
  try {
    const r = await fetch('http://localhost:8002/stats');
    if (!r.ok) throw new Error();
    const s = await r.json();
    document.getElementById('m-total').textContent = Number(s.total).toLocaleString();
    document.getElementById('m-total-sub').textContent = s.anomalies + ' EWMA anomalies';
    document.getElementById('m-errors').textContent = Number(s.errors).toLocaleString();
    document.getElementById('m-errors-sub').textContent = s.total ? ((s.errors/s.total)*100).toFixed(1)+'% error rate' : '';
    document.getElementById('m-anomaly').textContent = s.last_critical ? fmtTs(s.last_critical) : 'none detected';
  } catch(e) {
    document.getElementById('m-total').textContent = allLogs.length;
    document.getElementById('m-total-sub').textContent = 'agent offline';
    document.getElementById('m-errors').textContent = allLogs.filter(l=>sevClass(l.severity)==='error').length;
    document.getElementById('m-errors-sub').textContent = '';
    document.getElementById('m-anomaly').textContent = 'agent offline';
  }
}"""

result = f[:start] + new + f[end:]
open(r'C:\Users\donar\OneDrive\Desktop\Git Hub Projects\log-intelligence-platform\dashboard.html', 'w', encoding='utf-8').write(result)
print('done')
