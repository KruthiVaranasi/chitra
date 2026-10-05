"""Image/text embedding with CLIP-family models from Hugging Face (SigLIP, CLIP).

torch and transformers are imported lazily so the rest of the package (and the
tests) work without them.
"""

import os
from typing import List

import numpy as np
from PIL import Image

from .config import DEFAULT_MODEL

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")


class Embedder:
    def __init__(self, model_name: str = DEFAULT_MODEL, device: str = None):
        import torch
        import transformers
        from transformers import AutoModel, AutoProcessor

        transformers.logging.set_verbosity_error()
        transformers.logging.disable_progress_bar()

        self.torch = torch
        self.name = model_name
        if device is None:
            if torch.cuda.is_available():
                device = "cuda"
            elif getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
                device = "mps"
            else:
                device = "cpu"
        self.device = device
        self.model = AutoModel.from_pretrained(model_name).to(device).eval()
        self.processor = AutoProcessor.from_pretrained(model_name)
        # SigLIP was trained on text padded to 64 tokens; CLIP uses dynamic padding.
        self.text_kwargs = (
            {"padding": "max_length", "max_length": 64} if "siglip" in model_name.lower() else {"padding": True}
        )

    def _to_numpy(self, out) -> np.ndarray:
        feats = out if isinstance(out, self.torch.Tensor) else out.pooler_output
        feats = feats / feats.norm(dim=-1, keepdim=True)
        return feats.float().cpu().numpy()

    def encode_images(self, images: List[Image.Image]) -> np.ndarray:
        inputs = self.processor(images=images, return_tensors="pt").to(self.device)
        with self.torch.inference_mode():
            return self._to_numpy(self.model.get_image_features(**inputs))

    def encode_text(self, texts: List[str]) -> np.ndarray:
        inputs = self.processor(text=texts, truncation=True, return_tensors="pt", **self.text_kwargs).to(self.device)
        with self.torch.inference_mode():
            return self._to_numpy(self.model.get_text_features(**inputs))
