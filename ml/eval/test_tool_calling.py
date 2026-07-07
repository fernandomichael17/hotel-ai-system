import json
import httpx
import os
import re
from pathlib import Path

# Load environment variables manually
env_path = Path(".env")
if env_path.exists():
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                key_val = line.split("=", 1)
                if len(key_val) == 2:
                    os.environ[key_val[0].strip()] = key_val[1].strip()

# ==========================================
# BAGIAN 1 - Definisi tool functions (mock)
# ==========================================

def check_room_availability(room_type: str = "", date: str = "", force_unavailable: bool = False) -> dict:
    """Simulasi cek ketersediaan kamar"""
    if force_unavailable:
        return {
            "available": False,
            "room_type": room_type,
            "date": date,
            "reason": "Kamar penuh untuk tanggal tersebut",
            "alternatives": ["standard", "deluxe"]
        }
    return {
        "available": True,
        "room_type": room_type,
        "date": date,
        "price_per_night": 850000
    }

def collect_booking_parameter(message: str, current_params: dict) -> dict:
    """Simulasi extract parameter dari pesan user"""
    # model mengisi params lewat tool call, langsung direturn
    return current_params

def validate_booking_parameters(params: dict) -> dict:
    """Cek apakah semua field wajib sudah ada"""
    required = ["guest_name", "check_in_date", "room_type"]
    missing = [f for f in required if not params.get(f)]
    return {
        "is_complete": len(missing) == 0,
        "missing_fields": missing
    }

def create_booking_draft(params: dict) -> dict:
    """Simulasi simpan booking ke database"""
    return {
        "booking_id": "TEST-001",
        "status": "draft",
        "params": params
    }

def notify_sales(booking_id: str, params: dict) -> dict:
    """Simulasi kirim notif ke sales"""
    return {
        "notified": True,
        "booking_id": booking_id,
        "channel": "whatsapp"
    }

# ==========================================
# BAGIAN 2 - Tool definitions
# ==========================================

BOOKING_TOOLS = [
  {
    "type": "function",
    "function": {
      "name": "check_room_availability",
      "description": "Cek ketersediaan kamar hotel untuk tanggal tertentu",
      "parameters": {
        "type": "object",
        "properties": {
          "room_type": {
            "type": "string",
            "description": "Tipe kamar: standard, deluxe, suite"
          },
          "date": {
            "type": "string", 
            "description": "Tanggal check-in yang diminta user"
          }
        },
        "required": ["room_type", "date"]
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "validate_booking_parameters",
      "description": "Validasi apakah semua parameter booking sudah lengkap",
      "parameters": {
        "type": "object",
        "properties": {
          "params": {
            "type": "object",
            "description": "Parameter booking yang sudah terkumpul sejauh ini",
            "properties": {
              "guest_name": {"type": "string"},
              "check_in_date": {"type": "string"},
              "check_out_date": {"type": "string"},
              "room_type": {"type": "string"},
              "num_guests": {"type": "integer"}
            },
            "required": ["guest_name", "check_in_date", "room_type"]
          }
        },
        "required": ["params"]
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "create_booking_draft",
      "description": "Simpan booking sebagai draft setelah semua parameter lengkap",
      "parameters": {
        "type": "object",
        "properties": {
          "params": {
            "type": "object",
            "description": "Parameter booking yang sudah lengkap dan tervalidasi"
          }
        },
        "required": ["params"]
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "notify_sales",
      "description": "Kirim notifikasi ke tim sales setelah booking draft dibuat",
      "parameters": {
        "type": "object",
        "properties": {
          "booking_id": {
            "type": "string",
            "description": "ID booking draft yang baru dibuat"
          },
          "params": {
            "type": "object",
            "description": "Detail booking untuk dikirim ke sales"
          }
        },
        "required": ["booking_id", "params"]
      }
    }
  }
]

# ==========================================
# BAGIAN 3 - Tool executor
# ==========================================

def execute_tool(tool_name: str, tool_args: dict) -> str:
    tools_map = {
        "check_room_availability": check_room_availability,
        "validate_booking_parameters": validate_booking_parameters,
        "create_booking_draft": create_booking_draft,
        "notify_sales": notify_sales
    }
    
    if tool_name not in tools_map:
        return json.dumps({"error": f"Tool '{tool_name}' tidak dikenal."})
        
    try:
        func = tools_map[tool_name]
        result = func(**tool_args)
        return json.dumps(result)
    except Exception as e:
        return json.dumps({"error": str(e)})

# ==========================================
# BAGIAN 4 - Conversation loop
# ==========================================

def parse_tool_calls(message: dict) -> list[dict]:
    parsed_calls = []
    
    # FORMAT A
    if message.get("tool_calls"):
        for tc in message["tool_calls"]:
            if "function" in tc:
                # Handle possible string args vs dict args safely
                args_str = tc["function"].get("arguments", "{}")
                try:
                    args = json.loads(args_str)
                except Exception:
                    args = {}
                parsed_calls.append({
                    "id": tc.get("id", "call_xml"),
                    "name": tc["function"]["name"],
                    "arguments": args,
                    "format": "A"
                })
                
    # FORMAT B
    content = message.get("content", "")
    if content and "<tool_call>" in content:
        blocks = re.findall(r'<tool_call>(.*?)</tool_call>', content, re.DOTALL)
        for block in blocks:
            func_match = re.search(r'<function=([^>]+)>', block)
            if func_match:
                func_name = func_match.group(1).strip()
                args = {}
                param_matches = re.findall(r'<parameter=([^>]+)>(.*?)</parameter>', block, re.DOTALL)
                for k, v in param_matches:
                    args[k.strip()] = v.strip()
                    
                parsed_calls.append({
                    "id": "call_xml",
                    "name": func_name,
                    "arguments": args,
                    "format": "B"
                })
                
    return parsed_calls

def run_booking_conversation(initial_message: str, user_replies: list[str], system_prompt: str, scenario_id: int, force_unavailable: bool = False) -> dict:
    messages = [{"role": "system", "content": system_prompt}]
    tool_sequence = []
    collected_params = {}
    total_llm_calls = 0
    turn_count = 1
    replies_used = 0
    
    print(f"\n[Skenario {scenario_id}] Turn {turn_count}: User mengirim pesan '{initial_message}'")
    messages.append({"role": "user", "content": initial_message})
    
    iteration = 0
    while iteration < 15:
        iteration += 1
        total_llm_calls += 1
        
        model_name = os.environ.get("LLM_MODEL_NAME", "hotel-llm")
        api_base = os.environ.get("LLM_API_BASE", "http://localhost:8000/v1")
        api_url = f"{api_base.rstrip('/')}/chat/completions"
        api_key = os.environ.get("LLM_API_KEY", "not-needed")
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        
        payload = {
            "model": model_name,
            "messages": messages,
            "tools": BOOKING_TOOLS,
            "temperature": 0.0
        }
        
        try:
            response = httpx.post(api_url, json=payload, headers=headers, timeout=60.0)
            if response.status_code != 200:
                print(f"  [Error API] Status Code: {response.status_code}")
                print(f"  [Error Body] {response.text}")
                return {
                    "success": False,
                    "tool_sequence": tool_sequence,
                    "final_response": f"Error {response.status_code}: {response.text}",
                    "collected_params": collected_params,
                    "total_llm_calls": total_llm_calls
                }
            response_data = response.json()
        except Exception as e:
            print(f"  [Exception] Gagal terhubung ke model: {e}")
            return {
                "success": False,
                "tool_sequence": tool_sequence,
                "final_response": f"Exception: {str(e)}",
                "collected_params": collected_params,
                "total_llm_calls": total_llm_calls
            }
            
        choice = response_data.get("choices", [{}])[0]
        message = choice.get("message", {})
        
        print(f"[Skenario {scenario_id}] Turn {turn_count}: Model response diterima")
        
        parsed_calls = parse_tool_calls(message)
        
        # Format pesan asisten untuk di-append kembali sesuai standard OpenAI API
        append_msg = {"role": "assistant"}
        if message.get("content"):
            append_msg["content"] = message["content"]
        else:
            append_msg["content"] = ""
            
        if message.get("tool_calls"):
            append_msg["tool_calls"] = message.get("tool_calls")
            
        messages.append(append_msg)
        
        if parsed_calls:
            for tool_call in parsed_calls:
                tool_name = tool_call["name"]
                print(f"[Skenario {scenario_id}] Turn {turn_count}: Tool call terdeteksi → {tool_name}")
                
                args = tool_call["arguments"]
                
                # Parse stringified JSON values (common in Format B XML)
                for key, val in args.items():
                    if isinstance(val, str) and (val.strip().startswith('{') or val.strip().startswith('[')):
                        try:
                            args[key] = json.loads(val)
                        except Exception:
                            pass
                            
                if tool_name in ["validate_booking_parameters", "create_booking_draft"] and "params" in args:
                    if isinstance(args["params"], dict):
                        collected_params.update(args["params"])
                        
                if tool_name == "check_room_availability" and force_unavailable:
                    args["force_unavailable"] = True
                    
                tool_result_str = execute_tool(tool_name, args)
                print(f"[Skenario {scenario_id}] Turn {turn_count}: Tool executed → {tool_result_str}")
                
                if not tool_result_str.startswith('{"error"'):
                    tool_sequence.append(tool_name)
                
                if tool_call["format"] == "A":
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "name": tool_name,
                        "content": tool_result_str
                    })
                else:
                    messages.append({
                        "role": "user",
                        "content": f"Hasil {tool_name}: {tool_result_str}"
                    })
                    
            if "notify_sales" in tool_sequence:
                print(f"[Skenario {scenario_id}] Turn {turn_count}: Booking selesai (notify_sales dipanggil)")
                break
        else:
            bot_text = message.get("content", "")
            print(f"[Skenario {scenario_id}] Turn {turn_count}: Bot membalas teks (tanpa tool call)")
            
            if replies_used < len(user_replies):
                next_reply = user_replies[replies_used]
                replies_used += 1
                turn_count += 1
                print(f"[Skenario {scenario_id}] Turn {turn_count}: User membalas '{next_reply}'")
                messages.append({"role": "user", "content": next_reply})
            else:
                print(f"[Skenario {scenario_id}] Turn {turn_count}: Tidak ada lagi balasan dari user, menghentikan loop.")
                break
                
    if iteration >= 15:
        print(f"[Skenario {scenario_id}] Turn {turn_count}: Maksimal iterasi tercapai (infinite loop prevention)")
            
    return {
        "success": True,
        "tool_sequence": tool_sequence,
        "final_response": messages[-1].get("content", ""),
        "collected_params": collected_params,
        "total_llm_calls": total_llm_calls
    }

# ==========================================
# BAGIAN 5 & 6 - Test Scenarios & Evaluasi
# ==========================================

def evaluate():
    system_prompt = (
        "Kamu adalah asisten booking hotel Metland.\n"
        "Tugasmu membantu tamu melakukan booking kamar.\n"
        "Gunakan tools yang tersedia untuk memvalidasi\n"
        "dan memproses booking.\n"
        "\n"
        "ATURAN PENTING:\n"
        "1. Selalu gunakan tools — jangan proses booking\n"
        "   hanya dengan teks\n"
        "2. Urutan wajib: cek availability DULU,\n"
        "   baru validate, baru create draft, baru notify\n"
        "3. Untuk referensi waktu relatif seperti 'besok',\n"
        "   'akhir pekan ini', 'minggu depan' — gunakan\n"
        "   apa adanya sebagai nilai parameter,\n"
        "   JANGAN minta tanggal spesifik\n"
        "4. Kalau parameter kurang → tanya user,\n"
        "   SATU pertanyaan saja per giliran\n"
        "5. Jangan buat draft booking sebelum\n"
        "   validate_booking_parameters return\n"
        "   is_complete: true\n"
        "6. Komunikasi selalu dalam Bahasa Indonesia\n"
        "\n"
        "Tools yang tersedia dan urutan penggunaannya:\n"
        "1. check_room_availability — selalu pertama\n"
        "2. validate_booking_parameters — setelah availability\n"
        "3. create_booking_draft — hanya kalau is_complete: true\n"
        "4. notify_sales — selalu setelah draft dibuat"
    )
    
    scenarios = [
        {
            "id": 1,
            "name": "Data lengkap dari awal",
            "initial_message": "Mau booking kamar Deluxe tanggal 15 Juli sampai 17 Juli atas nama Budi Santoso, 2 orang",
            "user_replies": [],
            "expected_tools": ["check_room_availability", "validate_booking_parameters", "create_booking_draft", "notify_sales"]
        },
        {
            "id": 2,
            "name": "Data tidak lengkap, butuh tanya balik",
            "initial_message": "Mau booking kamar",
            "user_replies": [
                "Deluxe",
                "15 Juli",
                "2 malam",
                "Atas nama Siti Rahayu",
                "2 orang"
            ],
            "expected_tools": ["validate_booking_parameters"]
        },
        {
            "id": 3,
            "name": "User sebut tanggal relatif",
            "initial_message": "Booking kamar Standard untuk besok atas nama Ahmad, 1 malam, 1 orang",
            "user_replies": [],
            "expected_tools": ["check_room_availability", "validate_booking_parameters", "create_booking_draft", "notify_sales"]
        },
        {
            "id": 4,
            "name": "User ganti informasi di tengah",
            "initial_message": "Mau booking Deluxe 20 Juli atas nama Hendra, 2 malam",
            "user_replies": [
                "Eh maaf, namanya Hendra Wijaya",
                "Dan kamarnya ganti ke Suite ya",
                "2 orang"
            ],
            "expected_tools": ["validate_booking_parameters", "create_booking_draft", "notify_sales"]
        },
        {
            "id": 5,
            "name": "Kamar tidak tersedia",
            "initial_message": "Mau booking Presidential Suite 31 Desember atas nama Kevin, 3 malam, 2 orang",
            "user_replies": [],
            "expected_tools": ["check_room_availability"],
            "force_unavailable": True,
            "expected_behavior": {
                "should_stop_after": "check_room_availability",
                "should_NOT_call": [
                    "validate_booking_parameters",
                    "create_booking_draft", 
                    "notify_sales"
                ],
                "should_offer_alternative": True
            }
        }
    ]
    
    results = []
    correct_sequences = 0
    total_calls = 0
    all_tools_called = {}
    
    for sc in scenarios:
        print(f"\n" + "="*50)
        print(f"Menjalankan Skenario {sc['id']}: {sc['name']}")
        print("="*50)
        
        result = run_booking_conversation(
            sc["initial_message"], 
            sc["user_replies"], 
            system_prompt, 
            sc["id"],
            sc.get("force_unavailable", False)
        )
        
        seq = result["tool_sequence"]
        
        # Mengevaluasi urutan logis sederhana
        logical = True
        if "create_booking_draft" in seq:
            draft_idx = seq.index("create_booking_draft")
            # Pastikan validate dan ketersediaan dilakukan sebelum buat draft
            if "validate_booking_parameters" not in seq[:draft_idx]:
                logical = False
                
        # Mengevaluasi apakah ada aksi tanya balik ke user (jika belum komplit datanya)
        # Indikator: multi-turn request, atau sempat divalidasi tapi tak lanjut buat draft saat turn awal
        asked_back = len(sc["user_replies"]) > 0 or ("validate_booking_parameters" in seq and "create_booking_draft" not in seq)
        
        sc_result = {
            "scenario_id": sc["id"],
            "scenario_name": sc["name"],
            "tool_sequence": seq,
            "expected_tools_subset": sc["expected_tools"],
            "is_logical": logical,
            "asked_back": asked_back,
            "total_llm_calls": result["total_llm_calls"],
            "final_response": result["final_response"],
            "collected_params": result["collected_params"],
            "success": result["success"]
        }
        
        results.append(sc_result)
        total_calls += result["total_llm_calls"]
        
        for t in seq:
            all_tools_called[t] = all_tools_called.get(t, 0) + 1
            
        print(f"\n--- Ringkasan Skenario {sc['id']} ---")
        print(f"Urutan Tool yang dipanggil: {seq}")
        print(f"Ekspektasi Tool Minimal: {sc['expected_tools']}")
        print(f"Urutan Logis (validasi -> draft)? {logical}")
        print(f"Ada indikasi tanya balik? {asked_back}")
        print(f"Jumlah LLM Calls: {result['total_llm_calls']}")
        print(f"Respons Akhir:\n{result['final_response']}")
    
    # Menghitung jumlah skenario dengan tool sequence yang sesuai harapan
    for r in results:
        seq = r["tool_sequence"]
        expected = r["expected_tools_subset"]
        
        sc_data = next((s for s in scenarios if s["id"] == r["scenario_id"]), None)
        
        if sc_data and "expected_behavior" in sc_data:
            beh = sc_data["expected_behavior"]
            is_correct = True
            
            # Check mandatory tools
            if beh.get("should_stop_after") not in seq:
                is_correct = False
                
            # Check forbidden tools
            for not_tool in beh.get("should_NOT_call", []):
                if not_tool in seq:
                    is_correct = False
                    
            # Check alternative offer in final text
            if beh.get("should_offer_alternative"):
                resp = r["final_response"].lower()
                if "standard" not in resp and "deluxe" not in resp:
                    is_correct = False
        else:
            is_correct = all(et in seq for et in expected)
            
        if is_correct:
            correct_sequences += 1
            r["sequence_matches_expected"] = True
        else:
            r["sequence_matches_expected"] = False
            
    summary = {
        "correct_sequences": correct_sequences,
        "total_scenarios": len(scenarios),
        "average_llm_calls": total_calls / len(scenarios) if len(scenarios) > 0 else 0,
        "tool_call_frequencies": all_tools_called
    }
    
    print("\n" + "="*50)
    print("HASIL EVALUASI KESELURUHAN")
    print("="*50)
    print(f"Skenario dengan sequence tool yang tepat : {summary['correct_sequences']} / {summary['total_scenarios']}")
    print(f"Rata-rata pemanggilan LLM per skenario   : {summary['average_llm_calls']:.2f}")
    print(f"Frekuensi pemanggilan tool               :\n{json.dumps(summary['tool_call_frequencies'], indent=4)}")
    
    output_file = Path("ml/eval/results/tool_calling_test.json")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    final_output = {
        "summary": summary,
        "details": results
    }
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(final_output, f, indent=4, ensure_ascii=False)
        
    print(f"\nHasil evaluasi lengkap telah disimpan ke file: {output_file}")

if __name__ == "__main__":
    evaluate()
