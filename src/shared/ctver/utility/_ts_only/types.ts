import { CompoundEffectManager } from "shared/ctver/base/ports/compound_effect_manager";
import { StatsManager } from "shared/ctver/base/ports/stats_manager";

export type BasicPorts = StatsManager | CompoundEffectManager;
export type possible_dict_keys = string | number | symbol;
