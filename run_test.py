import subprocess

result = subprocess.run(['python', '-m', 'src.main', '--pddikti-poc'], capture_output=True, text=True)
with open('pddikti_poc_output.txt', 'w', encoding='utf-8') as f:
    f.write(result.stdout)
    f.write("\n--- STDERR ---\n")
    f.write(result.stderr)
