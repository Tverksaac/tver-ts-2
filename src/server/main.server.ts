import { Players } from "@rbxts/services";
import { Character } from "shared/ctver/core/character";

task.wait(2);
const plr = Players.GetPlayers()[0];
if (plr) {
	const char = plr.Character;
	const tver_char = (char ? new Character(char) : undefined) as Character;
	tver_char.GetPort("StatManager").AddStat("");
	print(tver_char.GetPort("StatManager"));
}
