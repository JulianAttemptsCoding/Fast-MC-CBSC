from __future__ import annotations
import numpy as np


def wasserstein_1d(a,b):
    a=np.sort(np.asarray(a,dtype=float)); b=np.sort(np.asarray(b,dtype=float))
    if a.size==0 or b.size==0: return None
    q=np.linspace(0,1,max(a.size,b.size)); return float(np.trapezoid(np.abs(np.quantile(a,q)-np.quantile(b,q)),q))


def response_bins(kinetic,truth,generated,edges):
    rows=[]
    for low,high in zip(edges[:-1],edges[1:]):
        mask=(kinetic>=low)&(kinetic<high); n=int(mask.sum())
        row={'low':float(low),'high':float(high),'n':n}
        if n>=2:
            tm=truth[mask].mean(); gm=generated[mask].mean(); ts=truth[mask].std(); gs=generated[mask].std()
            row.update({'truth_mean':float(tm),'generated_mean':float(gm),'mean_bias_fraction':float((gm-tm)/max(abs(tm),1e-9)),'truth_std':float(ts),'generated_std':float(gs),'resolution_difference_fraction':float((gs-ts)/max(abs(ts),1e-9))})
        else:
            row.update({'truth_mean':None,'generated_mean':None,'mean_bias_fraction':None,'truth_std':None,'generated_std':None,'resolution_difference_fraction':None})
        rows.append(row)
    return rows


def layer_sums(cell,layer_index):
    out=np.zeros((cell.shape[0],int(layer_index.max())+1),dtype=np.float64)
    for i,l in enumerate(layer_index): out[:,l]+=cell[:,i]
    return out


def high_level_features(cell,layer_index,positions):
    total=cell.sum(axis=1); hits=(cell>0).sum(axis=1); layers=layer_sums(cell,layer_index)
    depth=(layers*np.arange(layers.shape[1])[None]).sum(axis=1)/np.maximum(total,1e-9)
    x=(cell*positions[None,:,0]).sum(axis=1)/np.maximum(total,1e-9); y=(cell*positions[None,:,1]).sum(axis=1)/np.maximum(total,1e-9)
    dx=positions[None,:,0]-x[:,None]; dy=positions[None,:,1]-y[:,None]
    radial_rms=np.sqrt((cell*(dx*dx+dy*dy)).sum(axis=1)/np.maximum(total,1e-9))
    sorted_energy=np.sort(cell,axis=1)[:,::-1]
    top1=sorted_energy[:,0]/np.maximum(total,1e-9)
    ecal=layers[:,0]/np.maximum(total,1e-9)
    late_start=max(1,layers.shape[1]*3//4); late=layers[:,late_start:].sum(axis=1)/np.maximum(total,1e-9)
    return np.stack([total,hits,depth,x,y,radial_rms,top1,ecal,late],axis=1)


def distribution_metrics(truth,generated,layer_index,positions,seed=0):
    names=['total_response_gev','hit_count','depth_centroid_layer','x_centroid_mm','y_centroid_mm','radial_rms_mm','top1_fraction','ecal_fraction','late_fraction']
    tf=high_level_features(truth,layer_index,positions); gf=high_level_features(generated,layer_index,positions)
    result={name:{'wasserstein':wasserstein_1d(tf[:,i],gf[:,i]),'truth_mean':float(np.mean(tf[:,i])),'generated_mean':float(np.mean(gf[:,i]))} for i,name in enumerate(names)}
    positive_t=truth[truth>0]; positive_g=generated[generated>0]
    result['positive_cell_energy_gev']={'wasserstein':wasserstein_1d(positive_t,positive_g),'truth_mean':float(np.mean(positive_t)) if positive_t.size else 0.0,'generated_mean':float(np.mean(positive_g)) if positive_g.size else 0.0}
    lt=layer_sums(truth,layer_index); lg=layer_sums(generated,layer_index)
    mean_t=lt.mean(axis=0); mean_g=lg.mean(axis=0)
    result['mean_longitudinal_profile']={'relative_l1':float(np.abs(mean_t-mean_g).sum()/max(np.abs(mean_t).sum(),1e-9)),'truth':mean_t.tolist(),'generated':mean_g.tolist()}
    if len(truth)>=4:
        rng=np.random.default_rng(seed); order=rng.permutation(len(truth)); half=len(order)//2
        a=tf[order[:half]]; b=tf[order[half:2*half]]
        result['truth_half_floor']={name:{'wasserstein':wasserstein_1d(a[:,i],b[:,i])} for i,name in enumerate(names)}
    else: result['truth_half_floor']=None
    return result


def c2st_auc(truth_features,generated_features,seed=0):
    try:
        from sklearn.ensemble import HistGradientBoostingClassifier
        from sklearn.metrics import roc_auc_score
        from sklearn.model_selection import train_test_split
    except ImportError: return None
    x=np.concatenate([truth_features,generated_features]); y=np.concatenate([np.zeros(len(truth_features)),np.ones(len(generated_features))])
    if len(np.unique(y))<2 or len(y)<40: return None
    xtr,xte,ytr,yte=train_test_split(x,y,test_size=0.3,random_state=seed,stratify=y)
    clf=HistGradientBoostingClassifier(max_iter=100,max_depth=4,learning_rate=0.08,random_state=seed).fit(xtr,ytr)
    return float(roc_auc_score(yte,clf.predict_proba(xte)[:,1]))
