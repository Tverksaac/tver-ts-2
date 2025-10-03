import { atom } from "@rbxts/charm";
import { CharacterInfo } from "./_ts_only/interfaces";

export const client_atom = atom<CharacterInfo | undefined>();