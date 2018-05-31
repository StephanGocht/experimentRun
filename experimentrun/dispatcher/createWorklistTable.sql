CREATE TABLE `exprun.worklist` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `workgroup` VARCHAR(45) NULL,
  `config_file` VARCHAR(255) NULL,
  `hash` BINARY(20) NULL,
  `aquired` TIMESTAMP NULL,
  `state` ENUM('open', 'processing', 'done') NOT NULL DEFAULT 'open',
  PRIMARY KEY (`id`));