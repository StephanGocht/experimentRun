CREATE TABLE `exprun.worklist` (
  `id` INT NOT NULL,
  `workgroup` VARCHAR(45) NULL,
  `config_file` VARCHAR(255) NULL,
  `hash` BINARY(20) NULL,
  `aquired` TIMESTAMP NULL,
  `state` ENUM('open', 'processing', 'done', 'error') NOT NULL,
  PRIMARY KEY (`id`));