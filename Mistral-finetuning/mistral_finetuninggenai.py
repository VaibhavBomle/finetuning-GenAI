# -*- coding: utf-8 -*-
"""Mistral FinetuningGenai.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1oadvhC4Pa97WQJa3a5hivQSb2kbSbu_d

**Install required library**
"""

!pip install accelerate

!pip install peft

!pip install bitsandbytes

!pip install trl py7zr auto-gptq optimum

!pip install git+https://github.com/huggingface/transformers

from huggingface_hub import notebook_login

# Take token from hugging face
notebook_login()

import torch

from datasets import load_dataset,Dataset

data = load_dataset("samsum",split="train")

datadf = data.to_pandas()

datadf.head()

datadf_50 = datadf.sample(50)

datadf_50["text"] = datadf_50[["dialogue","summary"]].apply(lambda x: "###Human: Summarize this following dialogue: " + x["dialogue"] + "\n###Assistant: " + x["summary"], axis=1)

datadf_50["text"]

data = Dataset.from_pandas(datadf_50) # Provide a specific formate

from transformers import AutoModelForCausalLM,AutoTokenizer,GPTQConfig,TrainingArguments

tokenizer = AutoTokenizer.from_pretrained("TheBloke/Mistral-7B-Instruct-v0.1-GPTQ")

tokenizer.eos_token

tokenizer.pad_token=tokenizer.eos_token

quantization_config_loading = GPTQConfig(bits=4,disable_exllama=True,tokenizer=tokenizer)

# loading Quantized model
model =AutoModelForCausalLM.from_pretrained("TheBloke/Mistral-7B-Instruct-v0.1-GPTQ",
                                     quantization_config = quantization_config_loading,
                                     device_map = "auto")

print(model)

# configure parameter in model
model.config.use_cache=False
model.config.pretraining_tp=1
model.gradient_checkpointing_enable()

from peft import prepare_model_for_kbit_training

model = prepare_model_for_kbit_training(model)

from peft import LoraConfig

# Lora configuration for targeting specific parameter
peft_config = LoraConfig(
    r=16,lora_alpha=16,lora_dropout=0.05,bias="none",task_type="CAUSAL_LM",target_modules=["q_proj","v_proj"]
)

from peft import get_peft_model

model=get_peft_model(model,peft_config)

from trl import SFTTrainer # Imported Supervised Fine Tunning trainer

from transformers import TrainingArguments

training_arguments = TrainingArguments(
    output_dir="mistral-finetuned-samsum",
    per_device_train_batch_size=8,
    gradient_accumulation_steps=1,
    optim="paged_adamw_32bit",
    learning_rate=2e-4,
    lr_scheduler_type="cosine",
    save_strategy="epoch",
    logging_steps=100,
    num_train_epochs=1,
    max_steps=250,
    fp16=True,
    push_to_hub=True
)

"""Provide Write access for hugging face token"""

trainer = SFTTrainer(
    model=model,
    train_dataset=data,
    peft_config=peft_config,
    dataset_text_field="text",
    args=training_arguments,
    packing=False,
    max_seq_length=512
)

trainer.train()

# Push to huggingface hub
trainer.push_to_hub()

# command to push model in drive
!cp -r /content/mistral-finetuned-samsum /content/drive/MyDrive/

"""# **Infercening**"""

from peft import AutoPeftModelForCausalLM
from transformers import GenerationConfig
from transformers import AutoTokenizer
import torch

# Our trained tokenier model
tokenizer = AutoTokenizer.from_pretrained("/content/mistral-finetuned-samsum")

input = tokenizer("""
### Human: Summarize this following dialogue: Vasant: I'm at the railway station in Chennai Karthik: No problems so far? Vasanth
### Assistant: """,return_tensors="pt").to("cuda")

model = AutoPeftModelForCausalLM.from_pretrained(
    "/content/mistral-finetuned-samsum",
    low_cpu_mem_usage=True,
    return_dict=True,
    return_dict=True,
    torch_dtype=torch.float16,
    device_maps="cuda"
)

generation_config = GenerationConfig(
    do_sample=True,
    top_k=1,
    temperature=0.1,
    max_new_tokens=25,
    pad_token_id=tokenizer.eos_token_id
)

import time
st_time = time.time()
outputs = model.generate(**inputs,generation_config=generation_config)
print(tokenizer.decode(outputs[0],skip_special_tokens=True))
print(time.time()-st_time)