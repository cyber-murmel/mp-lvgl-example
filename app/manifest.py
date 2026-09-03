include("$(MPY_DIR)/extmod/asyncio")
require("aiorepl")
module("lv_utils.py", base_path="$(LV_BINDING_MICROPYTHON_DIR)/lib/")

require("lora")
require("lora-async")
require("lora-sx126x")

freeze("./frozen_modules")