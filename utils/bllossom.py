import transformers
import torch
import os
import time

# 가상환경이 아닌 경우 gpu 사용가능; espnet 가상환경에서는 cpu만 사용가능 ?
# huggingface-cli login
# (토큰은 절대 코드에 하드코딩하지 말 것)


PROMPT = '''당신은 유용한 AI 어시스턴트입니다. 사용자의 질의에 대해 친절하고 정확하게 답변해야 합니다.
You are a helpful AI assistant, you'll need to answer users' queries in a
friendly and accurate manner.'''


def main():
    token = (
        os.getenv("HUGGING_FACE_HUB_TOKEN")
        or os.getenv("HUGGINGFACEHUB_API_TOKEN")
        or os.getenv("HUGGINGFACE_TOKEN")
    )
    if not token:
        raise RuntimeError(
            "Missing Hugging Face token. Set HUGGING_FACE_HUB_TOKEN (recommended) and re-run."
        )

    # GPU 설정
    if torch.cuda.is_available():
        # GPU 메모리 캐시 정리
        torch.cuda.empty_cache()

        # GPU 1번 사용 (0번은 다른 프로세스가 사용 중)
        torch.cuda.set_device(1)
        device = "cuda:1"
        print(f"GPU 사용: {torch.cuda.get_device_name(1)}")

        # GPU 메모리 사용량 확인
        total_memory = torch.cuda.get_device_properties(1).total_memory / 1024**3
        print(f"GPU 메모리: {total_memory:.1f} GB")
    else:
        device = "cpu"
        print("CUDA를 사용할 수 없습니다. CPU를 사용합니다.")

    model_id = "MLP-KTLim/llama3-Bllossom"

    pipeline = transformers.pipeline(
        "text-generation",
        model=model_id,
        model_kwargs={"torch_dtype": torch.bfloat16},
        device=device,  # 명시적으로 디바이스 지정
        token=token,
    )

    # pad_token 설정
    pipeline.tokenizer.pad_token = pipeline.tokenizer.eos_token

    # GPU 사용 확인
    print("=== 시스템 정보 ===")
    print(f"CUDA 사용 가능: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"GPU 개수: {torch.cuda.device_count()}")
        print(f"현재 GPU: {torch.cuda.current_device()}")
        print(f"GPU 이름: {torch.cuda.get_device_name()}")
        print(f"GPU 메모리: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
    else:
        print("CUDA를 사용할 수 없습니다. CPU를 사용합니다.")

    print(f"모델 디바이스: {next(pipeline.model.parameters()).device}")
    print("=" * 50)

    while True:
        user_input = input("질문을 입력하세요 (종료하려면 'exit' 입력): ")
        if user_input.lower() == "exit":
            break

        messages = [
            {"role": "system", "content": PROMPT},
            {"role": "user", "content": user_input}
        ]

        prompt = pipeline.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )

        print("생성된 프롬프트:")
        print(prompt)
        print("-" * 50)

        terminators = [
            pipeline.tokenizer.eos_token_id,
            pipeline.tokenizer.convert_tokens_to_ids("<|eot_id|>")
        ]

        print("생성 시작...")
        start_time = time.time()

        # GPU에서 최적화된 생성
        with torch.no_grad():  # 메모리 절약
            outputs = pipeline(
                prompt,
                max_new_tokens=512,
                eos_token_id=terminators,
                do_sample=True,
                temperature=0.8,
                top_p=0.9,
                repetition_penalty=1.1,
                pad_token_id=pipeline.tokenizer.eos_token_id,
                return_full_text=True
            )

        end_time = time.time()
        generation_time = end_time - start_time
        print(f"생성 완료! (소요시간: {generation_time:.2f}초)")

        # GPU 메모리 사용량 확인
        if torch.cuda.is_available():
            memory_used = torch.cuda.memory_allocated(1) / 1024**3
            print(f"GPU 메모리 사용량: {memory_used:.1f} GB")

        # 토큰 개수 계산
        generated_tokens = len(pipeline.tokenizer.encode(outputs[0]["generated_text"])) - len(
            pipeline.tokenizer.encode(prompt)
        )
        if generation_time > 0:
            tokens_per_second = generated_tokens / generation_time
            print(f"생성된 토큰: {generated_tokens}개, 속도: {tokens_per_second:.1f} tokens/sec")

        print("전체 출력:")
        print(repr(outputs[0]["generated_text"]))  # repr로 특수문자 확인
        print("-" * 50)

        answer = outputs[0]["generated_text"][len(prompt):].strip()
        print("답변:", answer if answer else "빈 응답이 생성되었습니다.")


if __name__ == "__main__":
    main()