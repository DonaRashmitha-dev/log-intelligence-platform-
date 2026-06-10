f = open(r'C:\Users\donar\OneDrive\Desktop\Git Hub Projects\log-intelligence-platform\dashboard.html', encoding='utf-8').read()
f = f.replace("queryBtn.textContent = '...';", "queryBtn.textContent = 'RUN';")
open(r'C:\Users\donar\OneDrive\Desktop\Git Hub Projects\log-intelligence-platform\dashboard.html', 'w', encoding='utf-8').write(f)
print('done')
