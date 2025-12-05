import { PassiveGenericParams } from "shared/tver/utility/_ts_only/types";
import { get_logger } from "shared/tver/utility/utils";

const LOG_KEY = "[PASSIVE]";
const log = get_logger(LOG_KEY);
const dlog = get_logger(LOG_KEY, true);

//Passives will be created around character wrappers, not themselves
export abstract class Passive<Params extends Partial<PassiveGenericParams> = {}> {}
