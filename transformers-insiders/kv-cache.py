import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
import time
import matplotlib.pyplot as plt
import numpy as np
import psutil
import seaborn as sns

class Sampler:
    def __init__(self , model_name : str ='gpt2-medium') -> None:

        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForCausalLM.from_pretrained(model_name).to("cpu").to(self.device)

    def encode(self, text):
        return self.tokenizer.encode(text, return_tensors='pt').to(self.device)

    def decode(self, ids):
        return self.tokenizer.decode(ids)

    def get_next_token_prob(self, input_ids: torch.Tensor):
        with torch.no_grad():
            logits = self.model(input_ids=input_ids).logits
        logits = logits[0, -1, :]
        return logits
    
class GreedySampler(Sampler):
    def __call__(self, prompt, max_new_tokens=10):
        predictions = []
        result = prompt
        timings = []
        memory_usage = []
        
        for i in range(max_new_tokens):
            start_time = time.time()
            
            input_ids = self.encode(result)
            next_token_probs = self.get_next_token_prob(input_ids=input_ids)
            
            id = torch.argmax(next_token_probs, dim=-1).item()
            result += self.decode(id)
            
            end_time = time.time()
            timings.append(end_time - start_time)
            memory_usage.append(psutil.Process().memory_info().rss / 1024 / 1024)
            predictions.append(next_token_probs[id].item())

        return result, timings, memory_usage

class KVCacheSampler(Sampler):
    def __call__(self, prompt, max_new_tokens=10):
        predictions = []
        result = prompt
        timings = []
        memory_usage = []
        
        # Initial encoding
        input_ids = self.encode(result)
        past_key_values = None
        
        for i in range(max_new_tokens):
            start_time = time.time()
            
            with torch.no_grad():
                outputs = self.model(input_ids=input_ids, past_key_values=past_key_values)
                past_key_values = outputs.past_key_values
            
            next_token_probs = outputs.logits[0, -1, :]
            id = torch.argmax(next_token_probs, dim=-1).item()
            
            input_ids = torch.tensor([[id]]).to(self.device)
            result += self.decode(id)
            
            end_time = time.time()
            timings.append(end_time - start_time)
            memory_usage.append(psutil.Process().memory_info().rss / 1024 / 1024)
            predictions.append(next_token_probs[id].item())

        return result, timings, memory_usage

def plot_comparison(cached_data, uncached_data):
    plt.style.use('dark_background')
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(15, 20))
    
    tokens = range(len(cached_data[1]))
    ax1.plot(tokens, cached_data[1], 'g-', label='With KV Cache', linewidth=2)
    ax1.plot(tokens, uncached_data[1], 'r-', label='Without KV Cache', linewidth=2)
    ax1.set_title('Token Generation Time')
    ax1.set_xlabel('Token Number')
    ax1.set_ylabel('Time (seconds)')
    ax1.legend()
    ax1.grid(True, alpha=0.2)
    
    ax2.plot(tokens, np.cumsum(cached_data[1]), 'g-', label='With KV Cache', linewidth=2)
    ax2.plot(tokens, np.cumsum(uncached_data[1]), 'r-', label='Without KV Cache', linewidth=2)
    ax2.set_title('Cumulative Processing Time')
    ax2.set_xlabel('Token Number')
    ax2.set_ylabel('Total Time (seconds)')
    ax2.legend()
    ax2.grid(True, alpha=0.2)
    
    ax3.plot(tokens, cached_data[2], 'g-', label='With KV Cache', linewidth=2)
    ax3.plot(tokens, uncached_data[2], 'r-', label='Without KV Cache', linewidth=2)
    ax3.set_title('Memory Usage')
    ax3.set_xlabel('Token Number')
    ax3.set_ylabel('Memory (MB)')
    ax3.legend()
    ax3.grid(True, alpha=0.2)
    
    plt.tight_layout()
    plt.savefig('kv_cache_comparison.png', bbox_inches='tight', facecolor='black')
    plt.show()

prompt = "The quick brown fox"
uncached_sampler = GreedySampler()
cached_sampler = KVCacheSampler()

uncached_result = uncached_sampler(prompt, max_new_tokens=20)
cached_result = cached_sampler(prompt, max_new_tokens=20)

plot_comparison(cached_result, uncached_result)