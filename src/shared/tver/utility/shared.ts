import { atom } from "@rbxts/charm";
import { CharacterInfo } from "./_ts_only/interfaces";

/** Client-local reactive atom of the current player's `CharacterInfo`. */
export const client_atom = atom<CharacterInfo | undefined>(undefined);
