import { Players } from "@rbxts/services";
import { Character } from "shared/ctver/core/character";

Players.PlayerAdded.Connect((plr) => {
	if (plr) {
		plr.CharacterAdded.Connect((char) => {
			const tver_char = (char ? new Character(char) : undefined) as Character;
			const sm = tver_char.GetPort("StatManager");
			sm.GetStat("WalkSpeed")?.Set(10);
		});
	}
});
