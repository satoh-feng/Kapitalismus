import base64
import requests
import os
import json

# ✅ API Key（输入自己的API）
api_key = ""

# ✅ 图片文件夹 & 输出路径
foto_folder = "/Users/satoh/Desktop/final doc/ENPF"
output_path = os.path.join(foto_folder, "description.jsonl")

print("🚀 启动批量图片分析脚本...")
print(f"🔎 扫描目录: {foto_folder}")
if not os.path.isdir(foto_folder):
    print("❌ 目录不存在，请检查 foto_folder 路径是否正确。")
    raise SystemExit(1)

# 遍历 ENPF 下 doc1 ~ doc17（以及容错的 duc*）中的所有图片
image_files = []
for root, dirs, files in os.walk(foto_folder):
    rel_root = os.path.relpath(root, foto_folder)
    # 只接受以 doc/duc 开头的一级子目录（兼容大小写 & 你的早期命名）
    top = rel_root.split(os.sep)[0] if rel_root != "." else ""
    if top and not top.lower().startswith(("doc", "duc")):
        continue
    for file in files:
        if file.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp')):
            image_files.append(os.path.join(root, file))

print(f"🖼️ 共发现 {len(image_files)} 张图片")
if not image_files:
    print("⚠️ 没有发现可处理的图片文件（支持: .jpg/.jpeg/.png/.bmp/.gif/.webp）。")
    print("👉 检查：1) 路径是否正确；2) 子文件夹是否包含图片；3) 扩展名大小写。")
    raise SystemExit(0)


# ✅ 编码图片
def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")

# ✅ 图像分析函数（自动生成关键词 + 分析）
def get_image_analysis(image_base64):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    # 🧠 更智能的前置词
    prompt_text = (
        "你将扮演一位图像内容分析专家，负责分析社交媒体中用于推广、展示、表达意图的图片。\n"
        "请根据上传的图片，判断这张图可能蕴含的核心意图或用途。\n\n"
        "接下来，请**自行提取 5–10 个有意义的关键词**（例如：专业性、真实感、商业意图、生活气息、社交属性、审美价值等），并为每个关键词输出以下格式：\n"
        "关键词：百分比（子项打分1、子项打分2、子项打分3...）\n"
        "示例：\n"
        "生活气息：82%（自然光线 4、场景真实 5、人物松弛度 3）\n\n"
        "请确保每项都有数值分析，关键词请根据图像自行定义。不要使用固定模板。"
    )

    payload = {
        "model": "gpt-4o",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt_text},
                    {"type": "image_url", "image_url": {
                        "url": f"data:image/jpeg;base64,{image_base64}"
                    }}
                ]
            }
        ],
        "max_tokens": 1200
    }

    try:
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=60
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except requests.exceptions.Timeout:
        print("⏱️ 请求超时（timeout），已跳过该图片。")
        return None
    except requests.exceptions.RequestException as e:
        print(f"❌ 请求失败: {e}")
        try:
            print("服务器返回：", response.text[:500])
        except Exception:
            pass
        return None

# ✅ 批量分析图像并写入 JSONL（递归遍历子文件夹）
with open(output_path, "w", encoding="utf-8") as jsonl_file:
    for image_path in image_files:
        rel_path = os.path.relpath(image_path, start=foto_folder)
        print(f"📷 正在处理: {rel_path}", flush=True)
        try:
            base64_img = encode_image(image_path)
        except Exception as e:
            print(f"❌ 读取图片失败: {rel_path} -> {e}")
            continue
        analysis = get_image_analysis(base64_img)
        if analysis:
            entry = {
                "file": rel_path,  # 相对路径，便于回溯到子文件夹
                "analysis": analysis
            }
            jsonl_file.write(json.dumps(entry, ensure_ascii=False) + "\n")
            print(f"✅ 已保存分析: {rel_path}")
        else:
            print(f"⚠️ 无法获取分析: {rel_path}")

print(f"\n🎉 全部完成，结果保存在: {output_path}")
print(f"📝 输出文件: {output_path}")