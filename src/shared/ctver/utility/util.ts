import { RunService } from "@rbxts/services";
import { __CONFIG__ } from "../config";

const __DEBUG__ = __CONFIG__.DEBUG_CONFIG.__DEBUG__;

/** Convert a Map's values to an array. */
export function map_to_array<K extends defined, V extends defined>(map: Map<K, V>): V[] {
	const array: V[] = [];

	map.forEach((value) => {
		array.push(value);
	});

	return array;
}
export function array_to_string(array: defined[], separator: string = ", "): string {
	let s = "";
	array.forEach((val, index) => {
		s = s + tostring(val) + (index + 1 === array.size() ? "" : separator);
	});
	return s;
}
/** True if running on client. */
export function is_client_context(): boolean {
	return RunService.IsClient();
}
/** True if running on server. */
export function is_server_context(): boolean {
	return RunService.IsServer();
}
/** Convenience label for current context. */
export function get_context_name(): "Server" | "Client" {
	return is_client_context() ? "Client" : "Server";
}

// id generator
let id = 0;
export function get_id(): number {
	id++;
	return id;
}

//Output
const LOG_KEY = "TVER";

export function log(text: unknown): true {
	print(LOG_KEY + text);
	return true;
}

export function wlog(text: unknown): true {
	warn(LOG_KEY + text);
	return true;
}

export function elog(text: unknown) {
	return error(LOG_KEY + text + "\nTRACEBACK:\n" + debug.traceback());
}

export function dlog(text: unknown) {
	if (__DEBUG__) log(text);
}

export function dwlog(text: unknown) {
	if (__DEBUG__) wlog(text);
}

export function delog(text: unknown) {
	if (__DEBUG__) elog(text);
}

export function get_logger(logger_key: string, debug = false) {
	const key = "[" + logger_key + "]" + (debug ? "[DEBUG]: " : ": ");
	return {
		l: (text: unknown) => {
			!debug ? log(key + text) : dlog(key + text);
		},
		w: (text: unknown) => {
			!debug ? wlog(key + text) : dwlog(key + text);
		},
		e: (text: unknown) => {
			!debug ? elog(key + text) : delog(key + text);
		},
		r: (text: unknown) => print(key, text),
	};
}

export function loggers(logger_key: string) {
	return (get_logger(logger_key, false), get_logger(logger_key, true));
}
