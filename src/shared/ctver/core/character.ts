import { Janitor } from "@rbxts/janitor";
import { get_id, get_logger } from "../utility/util";
import { Port } from "./port";
import { Component } from "./component";
import { __CONFIG__ } from "../config";
import Signal from "@rbxts/signal";
import { StatsManager } from "../base/ports/stats_manager";
import { CompoundEffectManager } from "../base/ports/compound_effect_manager";

const LOG_KEY = "CHARACTER";

const log = get_logger(LOG_KEY);
const dlog = get_logger(LOG_KEY, true);

/**
 * Types
 */

export class Character {
	public Id: number = get_id();

	public Model: Model;
	public Humanoid: Humanoid;

	private _connected_ports: Port<Component[]>[] = [];

	private _janitor: Janitor = new Janitor();

	public PortConnected = new Signal<(port: Port<Component[]>) => void>();
	public PortDisconnecting = new Signal<(port: Port<Component[]>) => void>();

	constructor(CharacterModel: Model) {
		const hum = CharacterModel.FindFirstChildWhichIsA("Humanoid");
		if (!hum) {
			error(`Cant create Character for ${CharacterModel.Name}. Humanoid was not found inside of it!`);
		}
		this.Model = CharacterModel;
		this.Humanoid = hum;

		this._setup();
	}

	public ListConnectedPorts(): Port<Component[]>[] {
		return this._connected_ports;
	}

	public AddPort<NewPort extends Port<Component[]>>(
		port: new (host: Character, ...args: unknown[]) => NewPort,
		...args: unknown[]
	): NewPort {
		const new_port = new port(this, ...args);
		this._connected_ports.push(new_port);
		this.PortConnected.Fire(new_port);
		return new_port;
	}

	public RemovePort(Key: string): void {
		//??
		const port = this.GetPort(Key);
		if (!port) {
			log.w(`${this.Model.Name} do not have port with key ${Key}!`);
			return;
		}
		this.PortDisconnecting.Fire(port);
		port.Destroy();
	} //??

	public GetPort(key: "StatManager"): StatsManager;
	public GetPort(key: "CompoundEffectManager"): CompoundEffectManager;
	public GetPort(key: string): Port<Component[]>;
	public GetPort<PredictedPort extends Port<Component[]>>(key: string): PredictedPort | undefined {
		let to_return;
		this._connected_ports.forEach((port) => {
			if (port.Key === key) {
				to_return = port;
				return;
			}
		});
		return to_return;
	}

	private _setup() {
		this.AddPort(StatsManager);
		this.AddPort(CompoundEffectManager);
	}

	public Destroy(): void {}
}
