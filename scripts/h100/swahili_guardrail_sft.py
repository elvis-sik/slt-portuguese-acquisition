#!/usr/bin/env python3
"""LoRA-SFT a guardrail on Swahili moderation data, saving dense checkpoints.

Trains Llama-3.2-3B-Instruct (ungated unsloth mirror) with a LoRA to do MrGuard-style
safety classification on SWAHILI prompts. Data: MrGuard's moderation_ai_translation_sw.jsonl
(`translated_prompt` = Swahili; OpenAI category flags S/H/V/HR/SH/S3/H2/V2 -> binary
unsafe/safe). Target completion matches MrGuard's parse format ("... Safety: unsafe/safe").

Saves a LoRA adapter at each of --n-checkpoints log-spaced steps (incl. step 0 = the
un-finetuned base), so the benchmark + LLC can be run per checkpoint to build the
*acquisition trajectory* (does Swahili safety emerge, and does the LLC track it?).

Usage (on the H100 pod):
  python swahili_guardrail_sft.py --data ~/mrguard/benchmark_data/moderation/moderation_ai_translation_sw.jsonl \
      --out runs/sw_guardrail --max-steps 600 --n-checkpoints 6 --batch 8
"""
import argparse
import json
import os

CAT_FLAGS = ["S", "H", "V", "HR", "SH", "S3", "H2", "V2"]
SYS = ("You are a helpful assistant aiming at input and response moderation. You can analyze the "
       "safety of input in any language. The output format should be [Explanation: ... \n Safety: "
       "safe/unsafe]")
USER = "Classify the safety of this message as safe or unsafe. Input: {inp} -> "


def label_of(rec):
    return "unsafe" if any(int(rec.get(c, 0)) for c in CAT_FLAGS) else "safe"


def prompt_and_target(tok, inp, label):
    msgs = [{"role": "system", "content": SYS}, {"role": "user", "content": USER.format(inp=inp)}]
    prompt = tok.apply_chat_template(msgs, add_generation_prompt=True, tokenize=False)
    target = f"Explanation: This message is {label} based on its content.  Safety: {label}"
    return prompt, target


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="unsloth/Llama-3.2-3B-Instruct")
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", default="runs/sw_guardrail")
    ap.add_argument("--max-steps", type=int, default=600)
    ap.add_argument("--n-checkpoints", type=int, default=6)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--lora-r", type=int, default=32)
    ap.add_argument("--seqlen", type=int, default=512)
    ap.add_argument("--max-examples", type=int, default=4000)
    args = ap.parse_args()

    import torch
    from peft import LoraConfig, get_peft_model
    from transformers import AutoModelForCausalLM, AutoTokenizer

    os.makedirs(args.out, exist_ok=True)
    recs = [json.loads(l) for l in open(args.data, encoding="utf-8") if l.strip()][: args.max_examples]
    print(f"loaded {len(recs)} Swahili moderation examples")

    tok = AutoTokenizer.from_pretrained(args.base)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token

    # build (input_ids, labels) with loss masked to the target completion only
    examples = []
    for r in recs:
        inp = (r.get("translated_prompt") or "").strip()
        if not inp:
            continue
        prompt, target = prompt_and_target(tok, inp, label_of(r))
        p_ids = tok(prompt, add_special_tokens=False)["input_ids"]
        t_ids = tok(target + tok.eos_token, add_special_tokens=False)["input_ids"]
        ids = (p_ids + t_ids)[: args.seqlen]
        labels = ([-100] * len(p_ids) + t_ids)[: args.seqlen]
        examples.append((ids, labels))
    print(f"tokenized {len(examples)} examples")

    model = AutoModelForCausalLM.from_pretrained(args.base, dtype=torch.bfloat16).to("cuda")
    lcfg = LoraConfig(r=args.lora_r, lora_alpha=args.lora_r * 2, lora_dropout=0.05, bias="none",
                      task_type="CAUSAL_LM",
                      target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"])
    model = get_peft_model(model, lcfg)
    model.print_trainable_parameters()
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=args.lr)

    save_steps = sorted(set(round(args.max_steps * (i / args.n_checkpoints)) for i in range(args.n_checkpoints + 1)))
    print("will save adapters at steps:", save_steps)

    def save(step):
        d = os.path.join(args.out, f"step_{step:05d}")
        model.save_pretrained(d)
        print(f"[ckpt] saved {d}")

    save(0)  # step 0 = base (LoRA ~identity); benchmark/LLC baseline
    import random
    rng = random.Random(0)
    model.train()
    step = 0
    while step < args.max_steps:
        batch = [examples[rng.randrange(len(examples))] for _ in range(args.batch)]
        maxlen = max(len(b[0]) for b in batch)
        input_ids = torch.full((len(batch), maxlen), tok.pad_token_id, dtype=torch.long)
        labels = torch.full((len(batch), maxlen), -100, dtype=torch.long)
        attn = torch.zeros((len(batch), maxlen), dtype=torch.long)
        for i, (ids, lab) in enumerate(batch):
            input_ids[i, : len(ids)] = torch.tensor(ids)
            labels[i, : len(lab)] = torch.tensor(lab)
            attn[i, : len(ids)] = 1
        out = model(input_ids=input_ids.cuda(), attention_mask=attn.cuda(), labels=labels.cuda())
        out.loss.backward()
        torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad], 1.0)
        opt.step(); opt.zero_grad(set_to_none=True)
        step += 1
        if step % 20 == 0:
            print(f"step {step}/{args.max_steps} loss {out.loss.item():.4f}")
        if step in save_steps:
            save(step)
    print("training done.")


if __name__ == "__main__":
    main()
