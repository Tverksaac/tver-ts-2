import { atom } from "@rbxts/charm";
import { CharacterInfo } from "./interfaces";

export const client_atom = atom<CharacterInfo | undefined>(undefined);