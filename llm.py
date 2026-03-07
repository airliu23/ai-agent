import requests
import json
import time

class llm:
    def __init__(self):
        self.api_url = "https://model.southchips.net/v1/chat/completions"
        # self.api_url = "https://127.0.0.1"
        self.model_path = "DeepSeek-V3.1-Terminus"
        self.headers = {
            "Content-Type": "application/json"
        }
        self.timeout = 60  # 请求超时时间（秒）

    def ask_llm(self, prompt):
        data = {
            "model": self.model_path,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,
            "stream": True
        }

        try:
            start_time = time.time()
            response = requests.post(
                self.api_url, 
                headers=self.headers, 
                json=data, 
                stream=True,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            # 解析拼接
            full_content = ""  # 存储最终完整的回复内容
            last_data_time = time.time()

            # 逐行读取响应流
            for line in response.iter_lines():
                # 检查总超时
                if time.time() - start_time > self.timeout:
                    return {"error": f"请求超时（{self.timeout}秒）"}
                
                # 检查数据流超时（5秒内没有新数据）
                if time.time() - last_data_time > 5:
                    return {"error": "数据流超时（5秒内无新数据）"}
                
                # 过滤空行
                if not line:
                    continue
                
                # 解码行内容，去除首尾空白
                line_str = line.decode("utf-8").strip()
                last_data_time = time.time()  # 更新最后数据时间
                
                # 过滤非data开头的行
                if not line_str.startswith("data: "):
                    continue
                
                # 提取data: 后面的内容
                data_str = line_str[len("data: "):].strip()
                
                # 结束标识，退出循环
                if data_str == "[DONE]":
                    break
                
                # 解析JSON，提取增量内容
                try:
                    chunk = json.loads(data_str)
                    # 提取增量文本片段
                    delta_content = chunk["choices"][0]["delta"].get("content", "")
                    if delta_content:  # 过滤空内容
                        full_content += delta_content
                except Exception as e:
                    # 跳过解析失败的块，避免程序崩溃
                    print(f"\n解析块失败: {e}, 块内容: {data_str}")
                    continue
            
            return full_content
        except requests.exceptions.Timeout:
            return {"error": f"请求超时（{self.timeout}秒）"}
        except requests.exceptions.RequestException as e:
            return {"error": f"请求错误: {str(e)}"}
        except json.JSONDecodeError as e:
            return {"error": f"解析响应错误: {str(e)}"}
        except Exception as e:
            return {"error": f"未知错误: {str(e)}"}
