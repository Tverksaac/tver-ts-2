import { EffectState } from "./types";

/** Roblox character instance with a `Humanoid` child. */
export interface CharacterInstance extends Instance {
	Humanoid: Humanoid;
}

/** Minimal info needed to represent an applied compound effect. */
export interface CompoundEffectInfo {
	id: number;
	carrier_id: number;
	state: EffectState;
	constructor_params: unknown[];
	start_params?: unknown[];
	resume_params?: unknown[];
	pause_params?: unknown[];
}
export interface SkillInfo {
	id: number;
}

export interface PassiveInfo {}
/** Minimal info needed to represent a character. */
export interface CharacterInfo {
	instance: Instance;
	id: number;

	skills: Map<string, SkillInfo>;
	compound_effects: Map<string, CompoundEffectInfo>;
}
