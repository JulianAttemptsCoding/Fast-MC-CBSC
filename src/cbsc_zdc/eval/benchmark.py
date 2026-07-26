from __future__ import annotations
import time
import torch


def benchmark_model(model,p4,warmup=10,iterations=50,profile_steps=8,share_steps=8):
    for _ in range(warmup): model.sample(p4,profile_steps,share_steps,seed=1)
    if p4.is_cuda: torch.cuda.synchronize()
    start=time.perf_counter()
    for i in range(iterations): model.sample(p4,profile_steps,share_steps,seed=i)
    if p4.is_cuda: torch.cuda.synchronize()
    elapsed=time.perf_counter()-start
    return {'batch_size':len(p4),'iterations':iterations,'total_seconds':elapsed,'milliseconds_per_batch':1000*elapsed/iterations,'milliseconds_per_event':1000*elapsed/(iterations*len(p4)),'profile_steps':profile_steps,'share_steps':share_steps,'device':str(p4.device)}
