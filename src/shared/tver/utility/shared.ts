import { atom } from "@rbxts/charm";
import { CharacterInfo } from "./_ts_only/interfaces";

const LOG_KEY = "[TVER]: "

export const client_atom = atom<CharacterInfo | undefined>(undefined);
export function log(text: string) {
    print(LOG_KEY + text)
}

export function wlog(text: string) {
    warn(LOG_KEY + text)
}

export function elog(text: string) {
    error(LOG_KEY + text + "\n" + debug.traceback())
}