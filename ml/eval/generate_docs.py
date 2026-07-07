import json
from pathlib import Path

def generate_markdown(json_file: str, output_file: str):
    if not Path(json_file).exists():
        print(f"Error: File {json_file} tidak ditemukan.")
        return
        
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    markdown = "# Dokumentasi Percakapan Tool Calling (No Think)\n\n"
    markdown += f"**Total Skenario:** {data['summary']['total_scenarios']}\n"
    markdown += f"**Skenario Berhasil:** {data['summary']['correct_sequences']}\n"
    markdown += f"**Rata-rata LLM Calls:** {data['summary']['average_llm_calls']}\n\n"
    markdown += "---\n\n"

    for scenario in data['details']:
        markdown += f"## Skenario {scenario['scenario_id']}: {scenario['scenario_name']}\n\n"
        markdown += f"**Apakah Meminta Klarifikasi (Tanya Balik)?** {'Ya' if scenario.get('asked_back') else 'Tidak'}\n"
        markdown += f"**Urutan Eksekusi Logis?** {'Ya' if scenario.get('is_logical') else 'Tidak'}\n"
        markdown += f"**Berhasil (Sesuai Ekspektasi)?** {'Ya' if scenario.get('sequence_matches_expected', scenario.get('success', False)) else 'Tidak'}\n\n"
        
        markdown += "### Riwayat Percakapan\n\n"
        
        messages = scenario.get("messages", [])
        if not messages:
            markdown += "> *(Riwayat pesan tidak tersedia. Pastikan script evaluasi yang baru sudah selesai dijalankan)*\n\n"
        
        for msg in messages:
            role = msg.get("role", "unknown").capitalize()
            content = msg.get("content", "")
            
            if role == "System":
                markdown += f"**💻 {role}:**\n> *(System prompt disembunyikan agar lebih rapi)*\n\n"
            elif role == "User":
                # Pisahkan respon format B (Tool Result Text) dari pesan user asli
                if content and content.startswith("Hasil "):
                    markdown += f"**🔧 {content}**\n\n"
                else:
                    markdown += f"**👤 {role}:**\n{content}\n\n"
            elif role == "Assistant":
                if content:
                    import re
                    # Hapus blok <think>...</think> jika ada
                    clean_content = re.sub(r'<think>.*?</think>\n*', '', content, flags=re.DOTALL | re.IGNORECASE)
                    # Jika model hanya memunculkan </think> (tanpa tag pembuka)
                    clean_content = re.sub(r'.*?</think>\s*', '', clean_content, flags=re.DOTALL | re.IGNORECASE)
                    
                    if clean_content.strip():
                        # Escape tag XML agar tampil dengan baik di Markdown jika format B
                        safe_content = clean_content.replace("<", "&lt;").replace(">", "&gt;")
                        markdown += f"**🤖 {role}:**\n{safe_content.strip()}\n\n"
                
                # Check for tool calls (Format A)
                tool_calls = msg.get("tool_calls", [])
                if tool_calls:
                    for tc in tool_calls:
                        func_name = tc.get("function", {}).get("name", "unknown")
                        args = tc.get("function", {}).get("arguments", "{}")
                        markdown += f"**⚙️ Tool Call (`{func_name}`):**\n```json\n{args}\n```\n\n"
            elif role == "Tool":
                name = msg.get("name", "unknown")
                markdown += f"**🔧 Hasil Tool (`{name}`):**\n```json\n{content}\n```\n\n"
                
        markdown += "---\n\n"

    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(markdown)
        
    print(f"Berhasil membuat dokumen markdown: {output_file}")

if __name__ == "__main__":
    generate_markdown(
        "ml/eval/results/tool_calling_test_no_think.json",
        "ml/eval/results/conversation_docs_no_think.md"
    )
