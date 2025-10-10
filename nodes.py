import os
import json
import torch
import numpy as np
from PIL import Image, ImageOps
from PIL.PngImagePlugin import PngInfo
import base64 # New import
import io # New import

import folder_paths
from nodes import SaveImage, LoadImage
import server # Import server
import asyncio # Import Import asyncio
from comfy.comfy_types import node_typing, ComfyNodeABC, InputTypeDict
from comfy.comfy_types.node_typing import IO
import comfy.utils
import comfy.sd



class _CozyGenDynamicTypes(str):
    basic_types = node_typing.IO.PRIMITIVE.split(",")

    def __eq__(self, other):
        return other in self.basic_types or isinstance(other, (list, _CozyGenDynamicTypes))

    def __ne__(self, other):
        return not self.__eq__(other)

CozyGenDynamicTypes = _CozyGenDynamicTypes("COZYGEN_DYNAMIC_TYPE")


class CozyGenDynamicInput(ComfyNodeABC):
    _NODE_CLASS_NAME = "CozyGenDynamicInput" # Link to custom JavaScript

    @classmethod
    def INPUT_TYPES(cls) -> InputTypeDict:
        return {
            "required": {
                "param_name": (IO.STRING, {"default": "Dynamic Parameter"}),
                "priority": (IO.INT, {"default": 10}),                
                "param_type": ([IO.STRING, IO.INT, IO.FLOAT, IO.BOOLEAN, "DROPDOWN"], {"default": IO.STRING}),
                "default_value": (IO.STRING, {"default": ""}),
            },
            "optional": {
                "add_randomize_toggle": (IO.BOOLEAN, {"default": False}),
                "choice_type": (IO.STRING, {"default": ""}),
                "display_bypass": (IO.BOOLEAN, {"default": False}),
            },
            "hidden": {
                "choices": (IO.STRING, {"default": ""}), # Used by JS for dropdowns
                "multiline": (IO.BOOLEAN, {"default": False}), # Used by JS for strings
                "min_value": (IO.FLOAT, {"default": 0.0}), # Used by JS for numbers
                "max_value": (IO.FLOAT, {"default": 1.0}), # Used by JS for numbers
                "step": (IO.FLOAT, {"default": 0.0}), # Used by JS for numbers
            }
        }

    RETURN_TYPES = (IO.ANY,) # Can return any type
    FUNCTION = "get_dynamic_value"

    CATEGORY = "CozyGen"

    def get_dynamic_value(self, param_name, priority, param_type, default_value, add_randomize_toggle=False, choice_type="", min_value=0.0, max_value=1.0, choices="", multiline=False, step=None, display_bypass=False):
        # Convert default_value based on param_type
        if param_type == IO.INT:
            try:
                value = int(default_value)
            except (ValueError, TypeError):
                value = 0  # Default to 0 if conversion fails
        elif param_type == IO.FLOAT:
            try:
                value = float(default_value)
            except (ValueError, TypeError):
                value = 0.0  # Default to 0.0 if conversion fails
        elif param_type == IO.BOOLEAN:
            value = str(default_value).lower() == "true"
        elif param_type == "DROPDOWN":
            value = default_value # For dropdowns, default_value is already the selected string
        else:  # STRING or any other type
            value = default_value
        return (value, )


class CozyGenBoolInput:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "param_name": (IO.STRING, {"default": "Bool Parameter"}),
                "priority": (IO.INT, {"default": 10}),                
                "value": (IO.BOOLEAN, { "default": False })
            },
        }

    RETURN_TYPES = (IO.BOOLEAN,) # Can return any type
    FUNCTION = "get_value"

    CATEGORY = "CozyGen/Static"

    def get_value(self, param_name, priority, value):
        return (value, )


class CozyGenImageInput(ComfyNodeABC):
    @classmethod
    def INPUT_TYPES(s) -> InputTypeDict:
        input_dir = folder_paths.get_input_directory()
        files = [f for f in os.listdir(input_dir) if os.path.isfile(os.path.join(input_dir, f))]
        files = folder_paths.filter_files_content_types(files, ["image"])
        
        return {
            "required": {
                "param_name": (IO.STRING, {"default": "Image Input"}),
                "priority": (IO.INT, { "default": 0 }),
                "image": (sorted(files), { "image_upload": True, "image_folder": "input" }),
            }
        }
    
    # The return types are now the standard IMAGE and MASK for ComfyUI image loaders.
    RETURN_TYPES = (IO.IMAGE, )
    FUNCTION = "load_image"
    CATEGORY = "CozyGen"

    def load_image(self, param_name, priority,  image : str):
        return (LoadImage.load_image(None, image)[0], )

        
class CozyGenOutput(SaveImage):
    def __init__(self):
        super().__init__()
        self.output_dir = folder_paths.get_output_directory()

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": (IO.IMAGE, ),
            },
            "optional": {
                "filename_prefix": (IO.STRING, {"default": "CozyGen/output"}),
            },
        }

    FUNCTION = "save_images"
    CATEGORY = "CozyGen"

    def save_images(self, images, filename_prefix="CozyGen/output"):
        results = super().save_images(images, filename_prefix)
        server_instance = server.PromptServer.instance

        if server_instance and results and 'ui' in results and 'images' in results['ui']:
            batch_images_data = []
            for saved_image in results['ui']['images']:
                image_url = f"/view?filename={saved_image['filename']}&subfolder={saved_image['subfolder']}&type={saved_image['type']}"
                batch_images_data.append({
                    "url": image_url,
                    "filename": saved_image['filename'],
                    "subfolder": saved_image['subfolder'],
                    "type": saved_image['type']
                })
            
            if batch_images_data:
                message_data = {
                    "status": "images_generated",
                    "images": batch_images_data
                }
                server_instance.send_sync("cozygen_batch_ready", message_data)
                print(f"CozyGen: Sent batch WebSocket message: {message_data}")

        return results


import imageio

class CozyGenVideoOutput:
    def __init__(self):
        self.output_dir = folder_paths.get_output_directory()
        self.type = "output"
        self.prefix_append = ""

    @classmethod
    def INPUT_TYPES(s):
        return {
        "required": {
            "images": (IO.IMAGE, ),
                "frame_rate": (IO.INT, {"default": 8, "min": 1, "max": 24}),
                "loop_count": (IO.INT, {"default": 0, "min": 0, "max": 100}),
                "filename_prefix": (IO.STRING, {"default": "CozyGen/video"}),
                "format": (["video/webm", "video/mp4", "image/gif"],),
                "pingpong": (IO.BOOLEAN, {"default": False}),
            },
        }

    RETURN_TYPES = ()
    FUNCTION = "save_video"
    OUTPUT_NODE = True

    CATEGORY = "CozyGen"

    def save_video(self, images, frame_rate, loop_count, filename_prefix="CozyGen/video", format="video/webm", pingpong=False):
        filename_prefix += self.prefix_append
        full_output_folder, filename, counter, subfolder, filename_prefix = folder_paths.get_save_image_path(filename_prefix, self.output_dir, images[0].shape[1], images[0].shape[0])
        results = list()
        
        if format == "image/gif":
            ext = "gif"
        elif format == "video/mp4":
            ext = "mp4"
        else:
            ext = "webm"

        file = f"{filename}_{counter:05}_.{ext}"
        
        # imageio requires uint8
        video_data = (images.cpu().numpy() * 255).astype(np.uint8)

        if pingpong:
            video_data = np.concatenate((video_data, video_data[-2:0:-1]), axis=0)

        if format == "image/gif":
            imageio.mimsave(os.path.join(full_output_folder, file), video_data, duration=(1000/frame_rate)/1000, loop=loop_count)
        else:
            imageio.mimsave(os.path.join(full_output_folder, file), video_data, fps=frame_rate)

        results.append({
            "filename": file,
            "subfolder": subfolder,
            "type": self.type
        })

        server_instance = server.PromptServer.instance
        if server_instance:
            for result in results:
                video_url = f"/view?filename={result['filename']}&subfolder={result['subfolder']}&type={result['type']}"
                message_data = {
                    "status": "video_generated",
                    "video_url": video_url,
                    "filename": result['filename'],
                    "subfolder": result['subfolder'],
                    "type": result['type']
                }
                server_instance.send_sync("cozygen_video_ready", message_data)
                print(f"CozyGen: Sent custom WebSocket message: {{'type': 'cozygen_video_ready', 'data': {message_data}}}")

        return { "ui": { "videos": results } }

import comfy.samplers

# Dynamically get model folder names
models_path = folder_paths.models_dir
model_folders = sorted([d.name for d in os.scandir(models_path) if d.is_dir()])
static_choices = ["sampler", "scheduler"]
all_choice_types = model_folders + static_choices

class CozyGenFloatInput:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "param_name": (IO.STRING, {"default": "Float Parameter"}),
                "priority": (IO.INT, {"default": 10}),
                "default_value": (IO.FLOAT, {"default": 1.0}),
                "min_value": (IO.FLOAT, {"default": 0.0}),
                "max_value": (IO.FLOAT, {"default": 1024.0}),
                "step": (IO.FLOAT, {"default": 0.1}),
                "add_randomize_toggle": (IO.BOOLEAN, {"default": False}),
            }
        }
    
    RETURN_TYPES = (IO.FLOAT,)
    FUNCTION = "get_value"
    CATEGORY = "CozyGen/Static"
    def get_value(self, param_name, priority, default_value, min_value, max_value, step, add_randomize_toggle):
        return (default_value,)

class CozyGenIntInput:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "param_name": (IO.STRING, {"default": "Int Parameter"}),
                "priority": (IO.INT, {"default": 10}),
                "default_value": (IO.INT, {"default": 1, "min": -9999999999, "max": 9999999999, "step": 1}),
                "min_value": (IO.INT, {"default": 0}),
                "max_value": (IO.INT, {"default": 9999999999, "max": 9999999999}),
                "step": (IO.INT, {"default": 1}),
                "add_randomize_toggle": (IO.BOOLEAN, {"default": False}),
            }
        }
    
    RETURN_TYPES = (IO.INT,)
    FUNCTION = "get_value"
    CATEGORY = "CozyGen/Static"
    def get_value(self, param_name, priority, default_value, min_value, max_value, step, add_randomize_toggle):
        return (default_value,)

class CozyGenStringInput:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "param_name": (IO.STRING, {"default": "String Parameter"}),
                "priority": (IO.INT, {"default": 10}),
                "default_value": (IO.STRING, { "default": "", "multiline": True }),
                "display_multiline": (IO.BOOLEAN, {"default": False}),
            }
        }
    
    RETURN_TYPES = (IO.STRING,)
    FUNCTION = "get_value"
    CATEGORY = "CozyGen/Static"
    def get_value(self, param_name, priority, default_value, display_multiline):
        return (default_value,)

class CozyGenChoiceInput:
    _NODE_CLASS_NAME = "CozyGenChoiceInput"
    @classmethod
    def INPUT_TYPES(cls):
        # Create a flat list of all possible choices for the initial dropdown
        all_choices = []
        for choice_type in all_choice_types:
            if choice_type == "sampler":
                all_choices.extend(comfy.samplers.KSampler.SAMPLERS)
            elif choice_type == "scheduler":
                all_choices.extend(comfy.samplers.KSampler.SCHEDULERS)
            else:
                try:
                    all_choices.extend(folder_paths.get_filename_list(choice_type))
                except KeyError:
                    pass # Ignore choice types that don't have a corresponding folder
        # Add a "None" option to be safe
        all_choices = ["None"] + sorted(list(set(all_choices)))

        return {
            "required": {
                "param_name": (IO.STRING, {"default": "Choice Parameter"}),
                "priority": (IO.INT, {"default": 10}),
                "choice_type": (all_choice_types,),
                "default_choice": (all_choices,),
                "display_bypass": (IO.BOOLEAN, {"default": False}),
            },
            "hidden": {
                "value": (IO.STRING, { "default": "" }) # This is the value from the web UI
            }
        }

    RETURN_TYPES = (node_typing.IO.ANY,)
    FUNCTION = "get_value"
    CATEGORY = "CozyGen/Static"

    def get_value(self, param_name, priority, choice_type, default_choice, display_bypass, value):
        # The `value` parameter comes from the frontend UI on generation.
        # If it's present, we use it. Otherwise, we use the default set in the node graph.
        final_value = value if value and value != "None" else default_choice

        # If the final value is still None or empty, try to get a fallback
        if not final_value or final_value == "None":
            if choice_type == "sampler":
                return (comfy.samplers.KSampler.SAMPLERS[0],)
            elif choice_type == "scheduler":
                return (comfy.samplers.KSampler.SCHEDULERS[0],)
            else:
                choices = folder_paths.get_filename_list(choice_type)
                if choices:
                    return (choices[0],)
        
        return (final_value,)

class CozyGenLoraInput:
    _NODE_CLASS_NAME = "CozyGenLoraInput"
    
    def __init__(self):
        self.loaded_lora = None
    
    @classmethod
    def get_choices(cls):
        return ["None"] + sorted([x for x in folder_paths.get_filename_list("loras") if not x.startswith("hidden/")])
    
    @classmethod
    def INPUT_TYPES(cls):

        return {
            "required": {
                "model": (IO.MODEL,),
                "param_name": (IO.STRING, {"default": "Lora Selector"}),
                "priority": (IO.INT, {"default": 10}),
                "lora_value": (CozyGenLoraInput.get_choices(), { "default": "None" }),
                "strength_value": (IO.FLOAT, { "default": 1.0, "min": -5.0, "max": 5.0, "step": 0.05 })
            },
        }

    
    RETURN_TYPES = (IO.MODEL,)
    FUNCTION = "get_value"
    CATEGORY = "CozyGen/Static"
    
    def load_lora(self, model, lora_name, strength):
        lora_path = folder_paths.get_full_path_or_raise("loras", lora_name)
        lora = None
        if self.loaded_lora is not None:
            if self.loaded_lora[0] == lora_path:
                lora = self.loaded_lora[1]
            else:
                self.loaded_lora = None

        if lora is None:
            lora = comfy.utils.load_torch_file(lora_path, safe_load=True)
            self.loaded_lora = (lora_path, lora)

        model_lora, _ = comfy.sd.load_lora_for_models(model, None, lora, strength, 0)
        # print("Loaded Lora", lora_path, strength)
        return (model_lora,)

    def get_value(self, model, param_name, priority, lora_value, strength_value):
        if lora_value not in CozyGenLoraInput.get_choices() or lora_value == "None" or strength_value == 0:
            return (model,)
        
        return self.load_lora(model, lora_value, strength_value)

class CozyGenMetaText(ComfyNodeABC):
    _NODE_CLASS_NAME = "CozyGenMetaText"
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "hidden": {
                "value": (IO.STRING, {"default": ""})
            }
        }
        
    RETURN_TYPES = (IO.STRING,)
    RETURN_NAMES = ("metadata",)
    FUNCTION = "get_value"
    CATEGORY = "CozyGen/Static"
    
    def get_value(self, value=""):
        return (value,)

NODE_CLASS_MAPPINGS = {
    "CozyGenOutput": CozyGenOutput,
    "CozyGenVideoOutput": CozyGenVideoOutput,
    "CozyGenDynamicInput": CozyGenDynamicInput,
    "CozyGenImageInput": CozyGenImageInput,
    "CozyGenFloatInput": CozyGenFloatInput,
    "CozyGenIntInput": CozyGenIntInput,
    "CozyGenStringInput": CozyGenStringInput,
    "CozyGenChoiceInput": CozyGenChoiceInput,
    "CozyGenLoraInput": CozyGenLoraInput,
    "CozyGenMetaText": CozyGenMetaText,
    "CozyGenBoolInput": CozyGenBoolInput
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "CozyGenOutput": "CozyGen Output",
    "CozyGenVideoOutput": "CozyGen Video Output",
    "CozyGenDynamicInput": "CozyGen Dynamic Input",
    "CozyGenImageInput": "CozyGen Image Input",
    "CozyGenFloatInput": "CozyGen Float Input",
    "CozyGenIntInput": "CozyGen Int Input",
    "CozyGenStringInput": "CozyGen String Input",
    "CozyGenChoiceInput": "CozyGen Choice Input",
    "CozyGenLoraInput": "CozyGen Lora Input",
    "CozyGenMetaText": "CozyGen Meta Text",
    "CozyGenBoolInput": "CozyGen Bool Input"
}
