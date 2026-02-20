import { Players } from "@rbxts/services";
import { StrengthStat } from "shared/ctver/base/prebuilt/Strength";
import { Character } from "shared/ctver/core/character";

Players.PlayerAdded.Connect((plr) => {
	if (plr) {
		plr.CharacterAdded.Connect((char) => {
			const tver_char = (char ? new Character(char) : undefined) as Character;
			const sm = tver_char.GetPort("StatManager");
			sm.GetStat("WalkSpeed")?.Set(10);
			sm.AddStat(StrengthStat);

			task.wait(5);

			const str_stat = sm.GetStat("Strength");

			print(str_stat?.GetState());
			str_stat?.Set(5);
			print(str_stat?.GetState());
		});
	}
});
