import { Players } from "@rbxts/services";
import { HealthStat } from "shared/ctver/base/prebuilt/health";
import { Character } from "shared/ctver/core/character";

task.wait(2);
const plr = Players.GetPlayers()[0];
if (plr) {
	const char = plr.Character;
	const tver_char = (char ? new Character(char) : undefined) as Character;
	const sm = tver_char.GetPort("StatManager");
	sm.GetStat("Health");
	print(sm);
}
